import base64
import contextlib
import hashlib
import os
from datetime import datetime
from typing import Any, ClassVar

import requests
from dotenv import load_dotenv

load_dotenv("local.env")


class UserStats:
    # Hardcoded values and user details
    USER_NAME = os.environ.get("USER_NAME", "bernard")
    OWNER_ID = os.environ.get("OWNER_ID", "")
    TOKENS: ClassVar[list[str]] = [
        t.strip()
        for t in [
            os.environ.get("ACCESS_TOKEN", ""),
            os.environ.get("ALT_ACCESS_TOKEN", ""),
            os.environ.get("GITHUB_TOKEN", ""),
        ]
        if t.strip()
    ]
    TOKEN_INDEX = 0
    SESSION: ClassVar[requests.Session] = requests.Session()

    # Additional static details of the user
    BIRTHDAY = "14-10-2000"
    OS = "macOS, Linux (CachyOS)"
    HOST = "MacBook Air (M1), Custom PC Rig"
    TERMINAL = "zsh, Kitty, Antigravity"
    FOCUS = "Deep Learning & Federated Systems"
    LANGUAGES_PROG = "Python, Java, TypeScript, C/C++"
    STACK_TOOLS = "Docker, PyTorch, FastAPI, Vite, NextJS"
    SOUNDTRACK = "R&B, Soul, Psychedelic Rock & Jazz"
    FUEL = "Freshly Ground Coffee & Chocolate Bar"
    HOBBIES = "Acoustic Guitar, Steam Games, Plants"
    PHILOSOPHY = "Train loss goes down, dopamine goes up ^_^"
    EMAIL = "bernardbdas@gmail.com"
    SOCIAL_HANDLE = "bernardbdas"
    WEBSITE = "https://bernardbdas.github.io"

    QUERY_COUNT: ClassVar[dict[str, int]] = {
        "follower_getter": 0,
        "graph_repos_stars": 0,
        "recursive_loc": 0,
        "loc_query": 0,
    }

    @classmethod
    def query_count_inc(cls, funct_id: str) -> None:
        cls.QUERY_COUNT[funct_id] += 1

    @classmethod
    def get_token(cls) -> str:
        if not cls.TOKENS:
            raise ValueError("No GitHub access token found. Please set ACCESS_TOKEN in local.env")
        return cls.TOKENS[cls.TOKEN_INDEX % len(cls.TOKENS)]

    @classmethod
    def rotate_token(cls) -> None:
        if len(cls.TOKENS) > 1:
            cls.TOKEN_INDEX = (cls.TOKEN_INDEX + 1) % len(cls.TOKENS)
            print(f"[UserStats] Switched to token index {cls.TOKEN_INDEX}")

    @classmethod
    def ensure_user_credentials(cls) -> None:
        if cls.USER_NAME:
            cls.USER_NAME = cls.USER_NAME.strip().strip("'\"")

        need_viewer = not cls.OWNER_ID or not cls.USER_NAME or "@" in cls.USER_NAME or " " in cls.USER_NAME
        if need_viewer:
            query = """query { viewer { id login } }"""
            res = cls.simple_request("get_viewer_info", query, {})
            viewer = res.json().get("data", {}).get("viewer", {})
            if viewer:
                v_id = str(viewer.get("id", "")).strip()
                v_login = str(viewer.get("login", "")).strip()
                if v_id and not cls.OWNER_ID:
                    cls.OWNER_ID = v_id
                if v_login and (not cls.USER_NAME or "@" in cls.USER_NAME or " " in cls.USER_NAME):
                    print(f"[UserStats] Resolved username from GitHub token: '{v_login}' (was '{cls.USER_NAME}')")
                    cls.USER_NAME = v_login

    @classmethod
    def get_owner_id(cls) -> str:
        if not cls.OWNER_ID:
            cls.ensure_user_credentials()
            if not cls.OWNER_ID:
                query = """query { viewer { id login } }"""
                res = cls.simple_request("get_owner_id", query, {})
                viewer = res.json().get("data", {}).get("viewer", {})
                cls.OWNER_ID = str(viewer.get("id", ""))
                if not cls.USER_NAME or "@" in cls.USER_NAME or " " in cls.USER_NAME:
                    cls.USER_NAME = str(viewer.get("login", cls.USER_NAME)).strip()
        return cls.OWNER_ID

    @classmethod
    def simple_request(
        cls,
        func_name: str,
        query: str,
        variables: dict[str, Any],
        retries: int | None = None,
    ) -> requests.Response:
        if retries is None:
            retries = max(2, len(cls.TOKENS))

        last_error = None
        for _ in range(retries):
            token = cls.get_token()
            headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github.v3+json"}
            try:
                response = cls.SESSION.post(
                    "https://api.github.com/graphql",
                    json={"query": query, "variables": variables},
                    headers=headers,
                    timeout=30,
                )
                if response.status_code == 200:
                    json_resp = response.json()
                    if "errors" in json_resp and not json_resp.get("data"):
                        err_msgs = [e.get("message", "") for e in json_resp.get("errors", [])]
                        if any("rate limit" in m.lower() for m in err_msgs):
                            cls.rotate_token()
                            continue
                        raise Exception(f"{func_name} GraphQL error: {json_resp['errors']}")
                    return response
                elif response.status_code in (401, 403, 429):
                    print(f"[UserStats] API warning ({response.status_code}) on {func_name}. Rotating token...")
                    cls.rotate_token()
                    last_error = f"{response.status_code} {response.text}"
                    continue
                else:
                    raise Exception(f"{func_name} failed with {response.status_code}: {response.text}")
            except requests.RequestException as e:
                last_error = str(e)
                cls.rotate_token()

        raise Exception(f"{func_name} failed after {retries} retries: {last_error}")

    @classmethod
    def follower_getter(cls) -> int:
        cls.query_count_inc("follower_getter")
        cls.ensure_user_credentials()
        query = """query($login: String!){user(login: $login){followers{totalCount}}}"""
        variables = {"login": cls.USER_NAME}
        request = cls.simple_request("follower_getter", query, variables)
        user_node = request.json().get("data", {}).get("user")
        if not user_node:
            v_query = """query { viewer { id login } }"""
            res_v = cls.simple_request("get_viewer_fallback", v_query, {})
            v_login = str(res_v.json().get("data", {}).get("viewer", {}).get("login", "")).strip()
            if v_login and v_login != cls.USER_NAME:
                cls.USER_NAME = v_login
                variables["login"] = v_login
                request = cls.simple_request("follower_getter", query, variables)
                user_node = request.json().get("data", {}).get("user")
        if not user_node or "followers" not in user_node:
            return 0
        return int(user_node["followers"]["totalCount"])

    @classmethod
    def graph_repos_stars(cls, count_type: str, owner_affiliation: list[str], cursor: str | None = None) -> int:
        cls.query_count_inc("graph_repos_stars")
        cls.ensure_user_credentials()
        query = """query ($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
            user(login: $login) {
                repositories(first: 100, after: $cursor, ownerAffiliations: $owner_affiliation) {
                    totalCount
                    edges {node {nameWithOwner stargazers{totalCount}}}
                    pageInfo {endCursor hasNextPage}}}}"""
        variables = {"owner_affiliation": owner_affiliation, "login": cls.USER_NAME, "cursor": cursor}
        request = cls.simple_request("graph_repos_stars", query, variables)
        user_node = request.json().get("data", {}).get("user")
        if not user_node:
            v_query = """query { viewer { id login } }"""
            res_v = cls.simple_request("get_viewer_fallback", v_query, {})
            v_login = str(res_v.json().get("data", {}).get("viewer", {}).get("login", "")).strip()
            if v_login and v_login != cls.USER_NAME:
                cls.USER_NAME = v_login
                variables["login"] = v_login
                request = cls.simple_request("graph_repos_stars", query, variables)
                user_node = request.json().get("data", {}).get("user")
        if not user_node or "repositories" not in user_node:
            return 0
        data = user_node["repositories"]
        if count_type == "repos":
            return int(data["totalCount"])
        stars: int = sum(int(node["node"]["stargazers"]["totalCount"]) for node in data["edges"])
        if data["pageInfo"]["hasNextPage"]:
            stars += cls.graph_repos_stars(count_type, owner_affiliation, data["pageInfo"]["endCursor"])
        return stars

    @classmethod
    def loc_query(
        cls,
        owner_affiliation: list[str],
        comment_size: int = 0,
        force_cache: bool = False,
        cursor: str | None = None,
        edges: list[dict[str, Any]] | None = None,
    ) -> list[Any]:
        if edges is None:
            edges = []
        cls.query_count_inc("loc_query")
        owner_id = cls.get_owner_id()
        query = """query ($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String, $author_id: ID) {
            user(login: $login) {
                repositories(first: 100, after: $cursor, ownerAffiliations: $owner_affiliation) {
                    edges {
                        node {
                            nameWithOwner
                            defaultBranchRef {
                                target {
                                    ... on Commit {
                                        history(author: {id: $author_id}) {
                                            totalCount
                                        }
                                    }
                                }
                            }
                        }
                    }
                    pageInfo {
                        endCursor
                        hasNextPage
                    }
                }
            }
        }"""
        variables = {
            "owner_affiliation": owner_affiliation,
            "login": cls.USER_NAME,
            "cursor": cursor,
            "author_id": owner_id,
        }
        request = cls.simple_request("loc_query", query, variables)
        user_node = request.json().get("data", {}).get("user")
        if not user_node:
            # Fallback to viewer login if USER_NAME was misconfigured in GitHub Secrets
            v_query = """query { viewer { id login } }"""
            res_v = cls.simple_request("get_viewer_fallback", v_query, {})
            v_login = str(res_v.json().get("data", {}).get("viewer", {}).get("login", "")).strip()
            if v_login and v_login != cls.USER_NAME:
                print(f"[UserStats] User '{cls.USER_NAME}' not found in loc_query. Retrying with viewer '{v_login}'...")
                cls.USER_NAME = v_login
                variables["login"] = v_login
                request = cls.simple_request("loc_query", query, variables)
                user_node = request.json().get("data", {}).get("user")
        if not user_node or "repositories" not in user_node:
            raise Exception(
                f"loc_query failed: could not resolve repositories for user '{cls.USER_NAME}': {request.text}"
            )
        repos = user_node["repositories"]
        edges += repos["edges"]
        if repos["pageInfo"]["hasNextPage"]:
            return cls.loc_query(owner_affiliation, comment_size, force_cache, repos["pageInfo"]["endCursor"], edges)
        return cls.cache_builder(edges, comment_size, force_cache)

    @classmethod
    def cache_builder(cls, edges: list[dict[str, Any]], comment_size: int, force_cache: bool) -> list[Any]:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        cached = True
        os.makedirs("cache", exist_ok=True)
        filename = f"cache/{hashlib.sha256(cls.USER_NAME.encode()).hexdigest()}.txt"

        cache_comment = ["This line is a comment block. Write whatever you want here.\n" for _ in range(comment_size)]
        cache_map = {}

        if os.path.exists(filename):
            try:
                with open(filename, encoding="utf-8") as f:
                    raw_lines = f.readlines()
                if len(raw_lines) >= comment_size:
                    cache_comment = raw_lines[:comment_size]
                    for line in raw_lines[comment_size:]:
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            cache_map[parts[0]] = parts
            except Exception as e:
                print(f"[UserStats] Note: Could not read existing cache ({e}).")

        tasks_to_fetch = []
        repo_order = []

        for edge in edges:
            node = edge["node"]
            name_with_owner = node["nameWithOwner"]
            repo_hash = hashlib.sha256(name_with_owner.encode()).hexdigest()
            repo_order.append((name_with_owner, repo_hash))

            ref = node.get("defaultBranchRef")
            target = ref.get("target") if ref else None
            history = target.get("history") if target else None
            user_commit_count = history.get("totalCount", 0) if history else 0

            # If the user has 0 commits in this repository, no commits to fetch
            if user_commit_count == 0:
                cache_map[repo_hash] = [repo_hash, "0", "0", "0", "0"]
                continue

            cached_entry = cache_map.get(repo_hash)
            if (
                not force_cache
                and cached_entry
                and len(cached_entry) >= 5
                and int(cached_entry[1]) == user_commit_count
            ):
                continue

            cached = False
            owner, repo_name = name_with_owner.split("/")
            tasks_to_fetch.append((owner, repo_name, repo_hash, user_commit_count))

        if tasks_to_fetch:
            print(f"[UserStats] Fetching lines of code for {len(tasks_to_fetch)} repositories...")

            def _fetch_worker(
                task: tuple[str, str, str, int],
            ) -> tuple[str, int, tuple[int, int, int], str | None]:
                owner, repo_name, r_hash, user_cnt = task
                try:
                    loc = cls.recursive_loc(owner, repo_name)
                    return r_hash, user_cnt, loc, None
                except Exception as ex:
                    return r_hash, user_cnt, (0, 0, 0), str(ex)

            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {executor.submit(_fetch_worker, t): t for t in tasks_to_fetch}
                for done_count, future in enumerate(as_completed(futures), 1):
                    t = futures[future]
                    r_hash, user_cnt, loc, err = future.result()
                    if err:
                        print(f"[UserStats] Warning: Failed fetching for {t[0]}/{t[1]}: {err}")
                    cache_map[r_hash] = [r_hash, str(user_cnt), str(loc[2]), str(loc[0]), str(loc[1])]
                    print(
                        f"[UserStats] [{done_count}/{len(tasks_to_fetch)}] {t[0]}/{t[1]}: {loc[2]} commits, +{loc[0]:,} / -{loc[1]:,}"
                    )

        final_lines = []
        loc_add = 0
        loc_del = 0
        for _, repo_hash in repo_order:
            entry = cache_map.get(repo_hash, [repo_hash, "0", "0", "0", "0"])
            final_lines.append(f"{' '.join(entry)}\n")
            loc_add += int(entry[3])
            loc_del += int(entry[4])

        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w", encoding="utf-8") as f:
            f.writelines(cache_comment)
            f.writelines(final_lines)

        return [loc_add, loc_del, loc_add - loc_del, cached]

    @classmethod
    def flush_cache(cls, edges: list[dict[str, Any]], filename: str, comment_size: int) -> None:
        data: list[str] = []
        if os.path.exists(filename):
            with open(filename, encoding="utf-8") as f:
                data = f.readlines()[:comment_size] if comment_size > 0 else []
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w", encoding="utf-8") as f:
            f.writelines(data)
            for node in edges:
                f.write(hashlib.sha256(node["node"]["nameWithOwner"].encode()).hexdigest() + " 0 0 0 0\n")

    @classmethod
    def recursive_loc(
        cls,
        owner: str,
        repo_name: str,
        data: Any = None,
        cache_comment: Any = None,
        addition_total: int = 0,
        deletion_total: int = 0,
        my_commits: int = 0,
        cursor: str | None = None,
    ) -> tuple[int, int, int]:
        cls.query_count_inc("recursive_loc")
        owner_id = cls.get_owner_id()
        query = """query ($repo_name: String!, $owner: String!, $cursor: String, $author_id: ID) {
            repository(name: $repo_name, owner: $owner) {
                defaultBranchRef {
                    target {
                        ... on Commit {
                            history(first: 100, after: $cursor, author: {id: $author_id}) {
                                totalCount
                                edges {
                                    node {
                                        deletions
                                        additions
                                    }
                                }
                                pageInfo {
                                    endCursor
                                    hasNextPage
                                }
                            }
                        }
                    }
                }
            }
        }"""
        variables = {"repo_name": repo_name, "owner": owner, "cursor": cursor, "author_id": owner_id}
        request = cls.simple_request("recursive_loc", query, variables)
        res_data = request.json().get("data", {})
        repo_data = res_data.get("repository") if res_data else None
        if not repo_data or not repo_data.get("defaultBranchRef"):
            return addition_total, deletion_total, my_commits

        target = repo_data["defaultBranchRef"].get("target")
        if not target or not target.get("history"):
            return addition_total, deletion_total, my_commits

        history = target["history"]
        for node in history.get("edges", []):
            my_commits += 1
            addition_total += int(node["node"]["additions"])
            deletion_total += int(node["node"]["deletions"])

        if not history.get("pageInfo", {}).get("hasNextPage"):
            return addition_total, deletion_total, my_commits
        return cls.recursive_loc(
            owner,
            repo_name,
            data,
            cache_comment,
            addition_total,
            deletion_total,
            my_commits,
            history["pageInfo"]["endCursor"],
        )

    @classmethod
    def commit_counter(cls, comment_size: int) -> int:
        filename = f"cache/{hashlib.sha256(cls.USER_NAME.encode()).hexdigest()}.txt"
        with open(filename) as f:
            data = f.readlines()
        data = data[comment_size:]
        return sum(int(line.split()[2]) for line in data)

    @classmethod
    def get_dots(cls, total_len: int, text_len: int) -> str:
        just_len = max(0, total_len - text_len)
        return "." * just_len if just_len > 0 else ""

    @classmethod
    def get_user_dots(cls, key: str, value: Any) -> str:
        just_len = max(0, 55 - len(key) - len(str(value)))
        return "." * just_len if just_len > 0 else ""

    @classmethod
    def calc_age(cls, birth_str: str) -> str:
        try:
            b = datetime.strptime(birth_str, "%d-%m-%Y")
        except ValueError:
            try:
                b = datetime.strptime(birth_str, "%d-%m-%Y")
            except ValueError:
                return "Unknown"
        now = datetime.now()
        years = now.year - b.year
        months = now.month - b.month
        days = now.day - b.day
        if days < 0:
            months -= 1
            days += 30
        if months < 0:
            years -= 1
            months += 12
        return f"{years} years, {months} months, {days} days"

    @classmethod
    def read_gif_base64(cls, gif_path: str) -> str:
        try:
            with open(gif_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except FileNotFoundError:
            return ""

    @staticmethod
    def escape_xml(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

    @classmethod
    def build_svg(
        cls,
        mode: str,
        commit_data: int,
        star_data: int,
        repo_data: int,
        contrib_data: int,
        follower_data: int,
        loc_data: list[Any],
    ) -> str:
        age_str = cls.calc_age(cls.BIRTHDAY)
        commit_str = f"{commit_data:,}"
        star_str = f"{star_data:,}"
        repo_str = f"{repo_data:,}"
        contrib_str = f"{contrib_data:,}"
        follower_str = f"{follower_data:,}"
        loc_str = f"{loc_data[2]:,}"
        loc_add_str = f"{loc_data[0]:,}"
        loc_del_str = f"{loc_data[1]:,}"

        gif_file = (
            "assets/coder-lego-dark.gif"
            if mode == "dark" and os.path.exists("assets/coder-lego-dark.gif")
            else "assets/coder-lego.gif"
        )
        gif_b64 = cls.read_gif_base64(gif_file)
        gif_data = f"data:image/gif;base64,{gif_b64}" if gif_b64 else ""

        social_str = f"GitHub / LinkedIn / X: @{cls.SOCIAL_HANDLE}"

        os_dots = cls.get_user_dots("OS", cls.OS)
        host_dots = cls.get_user_dots("Host", cls.HOST)
        shell_dots = cls.get_user_dots("Terminal / IDE", cls.TERMINAL)
        age_dots = cls.get_user_dots("Uptime", age_str)

        focus_dots = cls.get_user_dots("Focus", cls.FOCUS)
        lang_prog_dots = cls.get_user_dots("Languages.Prog", cls.LANGUAGES_PROG)
        stack_tools_dots = cls.get_user_dots("Stack.Tools", cls.STACK_TOOLS)

        soundtrack_dots = cls.get_user_dots("Soundtrack", cls.SOUNDTRACK)
        fuel_dots = cls.get_user_dots("Fuel", cls.FUEL)
        hobbies_dots = cls.get_user_dots("Hobbies", cls.HOBBIES)
        philosophy_dots = cls.get_user_dots("Philosophy", cls.PHILOSOPHY)

        web_dots = cls.get_user_dots("Web", cls.WEBSITE)
        mail_dots = cls.get_user_dots("Mail", cls.EMAIL)
        social_dots = cls.get_user_dots("Social", social_str)

        repo_dots = cls.get_dots(5, len(repo_str))
        star_dots = cls.get_dots(8, len(star_str))
        commit_dots = cls.get_dots(8, len(commit_str))
        follower_dots = cls.get_dots(8, len(follower_str))
        loc_dots = cls.get_dots(10, len(loc_str))

        col1_line1_len = 13 + 15 + len(contrib_str) + 2
        col1_line2_len = 10 + len(commit_dots) + len(commit_str)
        commit_pad = " " * max(1, col1_line1_len - col1_line2_len)

        os_escaped = cls.escape_xml(cls.OS)
        host_escaped = cls.escape_xml(cls.HOST)
        shell_escaped = cls.escape_xml(cls.TERMINAL)
        focus_escaped = cls.escape_xml(cls.FOCUS)
        lang_prog_escaped = cls.escape_xml(cls.LANGUAGES_PROG)
        stack_tools_escaped = cls.escape_xml(cls.STACK_TOOLS)
        soundtrack_escaped = cls.escape_xml(cls.SOUNDTRACK)
        fuel_escaped = cls.escape_xml(cls.FUEL)
        hobbies_escaped = cls.escape_xml(cls.HOBBIES)
        philosophy_escaped = cls.escape_xml(cls.PHILOSOPHY)
        web_escaped = cls.escape_xml(cls.WEBSITE)
        mail_escaped = cls.escape_xml(cls.EMAIL)
        social_escaped = cls.escape_xml(social_str)

        box_width = 1000
        box_height = 580

        if mode == "dark":
            text_fill = "#8b949e"
            prompt_fill = "#7ee787"
            header_fill = "#79c0ff"
            key_fill = "#ffa657"
            value_fill = "#a5d6ff"
            add_fill = "#3fb950"
            del_fill = "#f85149"
            cc_fill = "#484f58"
            rect_fill = "#161b22"
            ansi_row1 = ["#484f58", "#ff7b72", "#7ee787", "#d29922", "#58a6ff", "#bc8cff", "#39c5cf", "#b1bac4"]
            ansi_row2 = ["#6e7681", "#ffa198", "#56d364", "#e3b341", "#79c0ff", "#d2a8ff", "#56d4dd", "#f0f6fc"]
        else:
            text_fill = "#57606a"
            prompt_fill = "#1a7f37"
            header_fill = "#0969da"
            key_fill = "#953800"
            value_fill = "#0a3069"
            add_fill = "#1a7f37"
            del_fill = "#cf222e"
            cc_fill = "#d0d7de"
            rect_fill = "#ffffff"
            ansi_row1 = ["#24292f", "#cf222e", "#1a7f37", "#9a6700", "#0969da", "#8250df", "#1b7c83", "#6e7781"]
            ansi_row2 = ["#57606a", "#a40e26", "#116329", "#633c01", "#0550ae", "#6639ba", "#114b5f", "#8c959f"]

        swatches = []
        for i, color in enumerate(ansi_row1):
            swatches.append(f'    <rect x="{390 + i * 27}" y="534" width="22" height="10" rx="2" fill="{color}" />')
        for i, color in enumerate(ansi_row2):
            swatches.append(f'    <rect x="{390 + i * 27}" y="548" width="22" height="10" rx="2" fill="{color}" />')
        ansi_swatches_svg = "\n".join(swatches)

        svg_parts = [
            "<?xml version='1.0' encoding='UTF-8'?>",
            f'<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback,Consolas,monospace" width="{box_width}px" height="{box_height}px" font-size="16px">',
            "<style>",
            "@font-face {",
            "  src: local('Consolas'), local('Consolas Bold');",
            "  font-family: 'ConsolasFallback';",
            "  font-display: swap;",
            "  -webkit-size-adjust: 109%;",
            "  size-adjust: 109%;",
            "}",
            f".key {{fill: {key_fill};}}",
            f".value {{fill: {value_fill};}}",
            f".addColor {{fill: {add_fill};}}",
            f".delColor {{fill: {del_fill};}}",
            f".cc {{fill: {cc_fill};}}",
            f".prompt {{fill: {prompt_fill};}}",
            f".header {{fill: {header_fill}; font-weight: bold;}}",
            "text, tspan {white-space: pre;}",
            "</style>",
            f'<rect width="{box_width}px" height="{box_height}px" fill="{rect_fill}" rx="15" />',
            f'<image x="15" y="40" width="350" height="500" href="{gif_data}" />',
            f'<text x="390"  y="30" fill="{text_fill}">',
            f'  <tspan x="390"  y="30" class="prompt">{cls.USER_NAME}@BERNARDs-MacBook-Air:~$ </tspan><tspan class="value">neofetch</tspan><tspan class="cc"> --profile -———————————————————————-—</tspan>',
            f'  <tspan x="390"  y="52" class="cc">. </tspan><tspan class="key">OS</tspan>:<tspan class="cc">{os_dots}</tspan><tspan class="value">{os_escaped}</tspan>',
            f'  <tspan x="390"  y="74" class="cc">. </tspan><tspan class="key">Host</tspan>:<tspan class="cc">{host_dots}</tspan><tspan class="value">{host_escaped}</tspan>',
            f'  <tspan x="390"  y="96" class="cc">. </tspan><tspan class="key">Shell / Terminal</tspan>:<tspan class="cc">{shell_dots}</tspan><tspan class="value">{shell_escaped}</tspan>',
            f'  <tspan x="390"  y="118" class="cc">. </tspan><tspan class="key">Uptime</tspan>:<tspan class="cc">{age_dots}</tspan><tspan class="value">{age_str}</tspan>',
            '  <tspan x="390"  y="144" class="header">- Focus &amp; Stack</tspan><tspan class="cc"> -————————————————————————————————————————————-—</tspan>',
            f'  <tspan x="390"  y="166" class="cc">. </tspan><tspan class="key">Focus</tspan>:<tspan class="cc">{focus_dots}</tspan><tspan class="value">{focus_escaped}</tspan>',
            f'  <tspan x="390"  y="188" class="cc">. </tspan><tspan class="key">Languages.Prog</tspan>:<tspan class="cc">{lang_prog_dots}</tspan><tspan class="value">{lang_prog_escaped}</tspan>',
            f'  <tspan x="390"  y="210" class="cc">. </tspan><tspan class="key">Stack.Tools</tspan>:<tspan class="cc">{stack_tools_dots}</tspan><tspan class="value">{stack_tools_escaped}</tspan>',
            '  <tspan x="390"  y="236" class="header">- Life &amp; Lore</tspan><tspan class="cc"> -——————————————————————————————————————————————-—</tspan>',
            f'  <tspan x="390"  y="258" class="cc">. </tspan><tspan class="key">Soundtrack</tspan>:<tspan class="cc">{soundtrack_dots}</tspan><tspan class="value">{soundtrack_escaped}</tspan>',
            f'  <tspan x="390"  y="280" class="cc">. </tspan><tspan class="key">Fuel</tspan>:<tspan class="cc">{fuel_dots}</tspan><tspan class="value">{fuel_escaped}</tspan>',
            f'  <tspan x="390"  y="302" class="cc">. </tspan><tspan class="key">Hobbies</tspan>:<tspan class="cc">{hobbies_dots}</tspan><tspan class="value">{hobbies_escaped}</tspan>',
            f'  <tspan x="390"  y="324" class="cc">. </tspan><tspan class="key">Philosophy</tspan>:<tspan class="cc">{philosophy_dots}</tspan><tspan class="value">{philosophy_escaped}</tspan>',
            '  <tspan x="390"  y="350" class="header">- Connect</tspan><tspan class="cc"> -——————————————————————————————————————————————————-—</tspan>',
            f'  <tspan x="390"  y="372" class="cc">. </tspan><tspan class="key">Web</tspan>:<tspan class="cc">{web_dots}</tspan><tspan class="value">{web_escaped}</tspan>',
            f'  <tspan x="390"  y="394" class="cc">. </tspan><tspan class="key">Mail</tspan>:<tspan class="cc">{mail_dots}</tspan><tspan class="value">{mail_escaped}</tspan>',
            f'  <tspan x="390"  y="416" class="cc">. </tspan><tspan class="key">Social</tspan>:<tspan class="cc">{social_dots}</tspan><tspan class="value">{social_escaped}</tspan>',
            '  <tspan x="390"  y="442" class="header">- GitHub Stats</tspan><tspan class="cc"> -————————————————————————————————————————————-—</tspan>',
            f'  <tspan x="390"  y="464" class="cc">. </tspan><tspan class="key">Repos</tspan>:<tspan class="cc">{repo_dots}</tspan><tspan class="value">{repo_str}</tspan> {{<tspan class="key">Contributed</tspan>: <tspan class="value">{contrib_str}</tspan>}} | <tspan class="key">Stars</tspan>:<tspan class="cc">{star_dots}</tspan><tspan class="value">{star_str}</tspan>',
            f'  <tspan x="390"  y="486" class="cc">. </tspan><tspan class="key">Commits</tspan>:<tspan class="cc">{commit_dots}</tspan><tspan class="value">{commit_str}</tspan>{commit_pad} | <tspan class="key">Followers</tspan>:<tspan class="cc">{follower_dots}</tspan><tspan class="value">{follower_str}</tspan>',
            f'  <tspan x="390"  y="508" class="cc">. </tspan><tspan class="key">Lines of Code</tspan>:<tspan class="cc">{loc_dots}</tspan><tspan class="value">{loc_str}</tspan> (<tspan class="addColor">{loc_add_str}</tspan><tspan class="addColor">++</tspan>, <tspan class="delColor">{loc_del_str}</tspan><tspan class="delColor">--</tspan>)</text>',
            '  <g id="ansi-palette">',
            f"{ansi_swatches_svg}",
            "  </g>",
            "</svg>",
        ]

        return "\n".join(svg_parts)

    @classmethod
    def generate_svgs(
        cls,
        commit_data: int,
        star_data: int,
        repo_data: int,
        contrib_data: int,
        follower_data: int,
        loc_data: list[Any],
        output_dir: str = "outputs",
    ) -> None:
        os.makedirs(output_dir, exist_ok=True)

        dark_svg = cls.build_svg("dark", commit_data, star_data, repo_data, contrib_data, follower_data, loc_data)
        light_svg = cls.build_svg("light", commit_data, star_data, repo_data, contrib_data, follower_data, loc_data)

        with open(os.path.join(output_dir, "dark_mode.svg"), "w", encoding="utf-8") as f:
            f.write(dark_svg)
        with open(os.path.join(output_dir, "light_mode.svg"), "w", encoding="utf-8") as f:
            f.write(light_svg)

    @classmethod
    def update_readme(cls, dark_svg_path: str, light_svg_path: str, readme_path: str = "README.md") -> None:
        import re

        with open(dark_svg_path, "rb") as f:
            dark_b64 = base64.b64encode(f.read()).decode("utf-8")
        with open(light_svg_path, "rb") as f:
            light_b64 = base64.b64encode(f.read()).decode("utf-8")

        dark_data_uri = f"data:image/svg+xml;base64,{dark_b64}"
        light_data_uri = f"data:image/svg+xml;base64,{light_b64}"

        with open(readme_path) as f:
            readme_content = f.read()

        readme_content = re.sub(
            r'<source media="\(prefers-color-scheme: dark\)" srcset="[^"]+">',
            f'<source media="(prefers-color-scheme: dark)" srcset="{dark_data_uri}">',
            readme_content,
        )
        readme_content = re.sub(
            r'<img alt="([^"]+)" src="[^"]+">', f'<img alt="\\1" src="{light_data_uri}">', readme_content
        )

        with open(readme_path, "w") as f:
            f.write(readme_content)


if __name__ == "__main__":
    UserStats.ensure_user_credentials()
    if os.path.exists("outputs"):
        for f in os.listdir("outputs"):
            if f.endswith(".svg"):
                with contextlib.suppress(FileNotFoundError):
                    os.remove(f"outputs/{f}")

    total_loc = UserStats.loc_query(["OWNER", "COLLABORATOR", "ORGANIZATION_MEMBER"], 7)
    commit_data = UserStats.commit_counter(7)
    star_data = UserStats.graph_repos_stars("stars", ["OWNER"])
    repo_data = UserStats.graph_repos_stars("repos", ["OWNER"])
    contrib_data = UserStats.graph_repos_stars("repos", ["OWNER", "COLLABORATOR", "ORGANIZATION_MEMBER"])
    follower_data = UserStats.follower_getter()

    UserStats.generate_svgs(
        commit_data, star_data, repo_data, contrib_data, follower_data, total_loc, output_dir="outputs"
    )
    # UserStats.update_readme('outputs/dark_mode.svg', 'outputs/light_mode.svg')
