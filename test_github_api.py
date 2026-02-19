import unittest
from unittest.mock import patch
from github_api import get_repos_and_commit_counts, GitHubApiError


class FakeResponse:
    def __init__(self, status_code, json_data, headers=None):
        self.status_code = status_code
        self._json_data = json_data
        self.headers = headers or {}

    def json(self):
        return self._json_data


class FakeSession:
    """
    A tiny fake requests.Session that returns canned responses by URL.
    """
    def __init__(self, responses_by_url):
        self.responses_by_url = responses_by_url
        self.calls = []

    def get(self, url, params=None, headers=None):
        self.calls.append((url, params or {}))
        # In our implementation, pagination "next" URLs come in fully formed.
        if url not in self.responses_by_url:
            return FakeResponse(404, {"message": "not found"})
        return self.responses_by_url[url]


class TestGitHubApi(unittest.TestCase):

    def test_happy_path_two_repos(self):
        user = "john567"
        repos_url = f"https://api.github.com/users/{user}/repos"
        commits_tri = f"https://api.github.com/repos/{user}/Triangle567/commits"
        commits_sq = f"https://api.github.com/repos/{user}/Square567/commits"

        fake = FakeSession({
            repos_url: FakeResponse(200, [{"name": "Triangle567"}, {"name": "Square567"}]),
            commits_tri: FakeResponse(200, [{}, {}, {}, {}, {}, {}, {}, {}, {}, {}]),  # 10
            commits_sq: FakeResponse(200, [{}] * 27),  # 27
        })

        with patch('github_api.requests.Session', return_value=fake):
            result = get_repos_and_commit_counts(user)

        self.assertIn(("Triangle567", 10), result)
        self.assertIn(("Square567", 27), result)
        self.assertEqual(len(result), 2)

    def test_invalid_user_id(self):
        with self.assertRaises(ValueError):
            get_repos_and_commit_counts("")

        with self.assertRaises(ValueError):
            get_repos_and_commit_counts(None)  # type: ignore

    def test_user_not_found_404(self):
        user = "no_such_user_123"
        repos_url = f"https://api.github.com/users/{user}/repos"

        fake = FakeSession({
            repos_url: FakeResponse(404, {"message": "Not Found"})
        })

        with patch('github_api.requests.Session', return_value=fake):
            with self.assertRaises(GitHubApiError) as ctx:
                get_repos_and_commit_counts(user)

        self.assertIn("404", str(ctx.exception))

    def test_rate_limit_403(self):
        user = "someone"
        repos_url = f"https://api.github.com/users/{user}/repos"

        fake = FakeSession({
            repos_url: FakeResponse(403, {"message": "rate limit"})
        })

        with patch('github_api.requests.Session', return_value=fake):
            with self.assertRaises(GitHubApiError) as ctx:
                get_repos_and_commit_counts(user)

        self.assertIn("rate limit", str(ctx.exception).lower())

    def test_repo_missing_name_is_skipped(self):
        user = "x"
        repos_url = f"https://api.github.com/users/{user}/repos"

        fake = FakeSession({
            repos_url: FakeResponse(200, [{"bad": "object"}, {"name": "GoodRepo"}]),
            f"https://api.github.com/repos/{user}/GoodRepo/commits": FakeResponse(200, [{}] * 3),
        })

        with patch('github_api.requests.Session', return_value=fake):
            result = get_repos_and_commit_counts(user)

        self.assertEqual(result, [("GoodRepo", 3)])

    def test_pagination_for_repos(self):
        user = "p"
        repos_url = f"https://api.github.com/users/{user}/repos"
        next_repos = "https://api.github.com/users/p/repos?page=2"

        fake = FakeSession({
            repos_url: FakeResponse(
                200,
                [{"name": "R1"}],
                headers={"Link": f'<{next_repos}>; rel="next"'}
            ),
            next_repos: FakeResponse(200, [{"name": "R2"}]),
            f"https://api.github.com/repos/{user}/R1/commits": FakeResponse(200, [{}]),
            f"https://api.github.com/repos/{user}/R2/commits": FakeResponse(200, [{}, {}]),
        })

        with patch('github_api.requests.Session', return_value=fake):
            result = get_repos_and_commit_counts(user)

        self.assertEqual(sorted(result), [("R1", 1), ("R2", 2)])


if __name__ == "__main__":
    unittest.main()
