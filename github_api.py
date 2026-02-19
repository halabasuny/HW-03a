import requests
import re


class GitHubApiError(Exception):
    """Custom exception for GitHub API errors"""
    pass


def get_repos_and_commit_counts(user, session=None):
    """
    Retrieve repositories and their commit counts for a GitHub user.

    Args:
        user: GitHub username
        session: Optional requests.Session object for dependency injection (testing)

    Returns:
        List of tuples: [(repo_name, commit_count), ...]

    Raises:
        GitHubApiError: If user not found (404) or rate limited (403)
        ValueError: If user is None or empty string
    """
    # Input validation
    if user is None or user == "":
        raise ValueError("User ID cannot be None or empty")

    if session is None:
        session = requests.Session()

    repos_and_counts = []
    url = f"https://api.github.com/users/{user}/repos"

    while url:
        response = session.get(url, params={"per_page": 100})

        # Handle error status codes
        if response.status_code == 404:
            raise GitHubApiError(f"404: User '{user}' not found")
        elif response.status_code == 403:
            raise GitHubApiError("403: rate limit exceeded")

        data = response.json()

        # If no more repos, break the loop
        if not data:
            break

        # Process each repo
        for repo in data:
            # Skip repos without a name
            if "name" not in repo or repo["name"] is None:
                continue

            repo_name = repo["name"]
            commits_url = f"https://api.github.com/repos/{user}/{repo_name}/commits"

            # Get commit count
            commits_response = session.get(commits_url, params={"per_page": 1})

            # Extract commit count
            commit_count = len(commits_response.json())

            repos_and_counts.append((repo_name, commit_count))

        # Check for next page in Link header
        url = _get_next_url(response)

    return repos_and_counts


def _get_next_url(response):
    """
    Extract the 'next' URL from the Link header if present.
    Returns None if no next link exists.
    """
    if "Link" not in response.headers:
        return None

    link_header = response.headers["Link"]
    # Look for rel="next" link
    match = re.search(r'<([^>]+)>;\s*rel="next"', link_header)
    if match:
        return match.group(1)

    return None
