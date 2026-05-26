import os
import hashlib
import base64
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv('local.env')


class UserStats:
    # Hardcoded values and user details
    USER_NAME = os.environ.get('USER_NAME', 'bernardbdas')
    OWNER_ID = os.environ.get('OWNER_ID', '')
    HEADERS = {'authorization': 'token ' + os.environ.get('ACCESS_TOKEN', '')}

    # Additional static details of the user
    BIRTHDAY = '14-10-2000'
    OS = 'macOS, Linux (CachyOS)'
    HOST = 'MacBook Air (M1), Custom PC'
    KERNEL = 'Machine Learning Enthusiast'
    IDE = 'VSCode, Xcode'
    LANGUAGES_PROG = 'Python, TypeScript, Java, C++'
    LANGUAGES_COMP = 'SQL, SHELL, HTML, CSS, JSON, YAML'
    LANGUAGES_REAL = 'English, Hindi, Bengali'
    EMAIL = 'bernardbdas@gmail.com'
    LINKEDIN = 'bernardbdas'
    TWITTER = 'bernardbdas'
    GITHUB = 'bernardbdas'
    WEBSITE = 'https://bernardbdas.github.io'
    DISCORD = 'bernardbdas'
    INSTAGRAM = 'therailroadmanshow'
    Hobbies_Software = 'Movies, Music, Reading'
    Hobbies_Hardware = 'Guitar, Gaming, Gardening'

    QUERY_COUNT = {
        'follower_getter': 0, 'graph_repos_stars': 0,
        'recursive_loc': 0, 'loc_query': 0
    }

    @classmethod
    def query_count_inc(cls, funct_id):
        cls.QUERY_COUNT[funct_id] += 1

    @classmethod
    def simple_request(cls, func_name, query, variables):
        request = requests.post('https://api.github.com/graphql',
                                json={'query': query, 'variables': variables}, headers=cls.HEADERS)
        if request.status_code == 200:
            json_resp = request.json()
            if 'errors' in json_resp or 'data' not in json_resp:
                raise Exception(f"{func_name} GraphQL error: {json_resp}")
            return request
        raise Exception(
            f"{func_name} has failed with a {request.status_code} {request.text} {cls.QUERY_COUNT}")

    @classmethod
    def follower_getter(cls):
        cls.query_count_inc('follower_getter')
        query = '''query($login: String!){user(login: $login){followers{totalCount}}}'''
        variables = {'login': cls.USER_NAME}
        request = cls.simple_request('follower_getter', query, variables)
        return int(request.json()['data']['user']['followers']['totalCount'])

    @classmethod
    def graph_repos_stars(cls, count_type, owner_affiliation, cursor=None):
        cls.query_count_inc('graph_repos_stars')
        query = '''query ($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
            user(login: $login) {
                repositories(first: 100, after: $cursor, ownerAffiliations: $owner_affiliation) {
                    totalCount
                    edges {node {nameWithOwner stargazers{totalCount}}}
                    pageInfo {endCursor hasNextPage}}}}'''
        variables = {'owner_affiliation': owner_affiliation,
                     'login': cls.USER_NAME, 'cursor': cursor}
        request = cls.simple_request('graph_repos_stars', query, variables)
        data = request.json()['data']['user']['repositories']
        if count_type == 'repos':
            return data['totalCount']
        return sum(node['node']['stargazers']['totalCount'] for node in data['edges'])

    @classmethod
    def loc_query(cls, owner_affiliation, comment_size=0, force_cache=False, cursor=None, edges=None):
        if edges is None:
            edges = []
        cls.query_count_inc('loc_query')
        query = '''query ($owner_affiliation: [RepositoryAffiliation], $login: String!, $cursor: String) {
            user(login: $login) {
                repositories(first: 60, after: $cursor, ownerAffiliations: $owner_affiliation) {
                edges {node {nameWithOwner defaultBranchRef {target {... on Commit {history {totalCount}}}}}}
                pageInfo {endCursor hasNextPage}}}}'''
        variables = {'owner_affiliation': owner_affiliation,
                     'login': cls.USER_NAME, 'cursor': cursor}
        request = cls.simple_request('loc_query', query, variables)
        repos = request.json()['data']['user']['repositories']
        edges += repos['edges']
        if repos['pageInfo']['hasNextPage']:
            return cls.loc_query(owner_affiliation, comment_size, force_cache, repos['pageInfo']['endCursor'], edges)
        return cls.cache_builder(edges, comment_size, force_cache)

    @classmethod
    def cache_builder(cls, edges, comment_size, force_cache):
        cached = True
        os.makedirs('cache', exist_ok=True)
        filename = f'cache/{hashlib.sha256(cls.USER_NAME.encode()).hexdigest()}.txt'
        try:
            with open(filename, 'r') as f:
                data = f.readlines()
        except FileNotFoundError:
            data = ['This line is a comment block. Write whatever you want here.\n' for _ in range(
                comment_size)]
            with open(filename, 'w') as f:
                f.writelines(data)

        if len(data) - comment_size != len(edges) or force_cache:
            cached = False
            cls.flush_cache(edges, filename, comment_size)
            with open(filename, 'r') as f:
                data = f.readlines()

        cache_comment = data[:comment_size]
        data = data[comment_size:]
        for i, edge in enumerate(edges):
            repo_hash = hashlib.sha256(
                edge['node']['nameWithOwner'].encode()).hexdigest()
            parts = data[i].split()
            if parts[0] == repo_hash:
                if int(parts[1]) != edge['node']['defaultBranchRef']['target']['history']['totalCount']:
                    owner, repo_name = edge['node']['nameWithOwner'].split('/')
                    loc = cls.recursive_loc(
                        owner, repo_name, data, cache_comment)
                    data[i] = f"{repo_hash} {edge['node']['defaultBranchRef']['target']['history']['totalCount']} {loc[2]} {loc[0]} {loc[1]}\n"
            else:
                data[i] = f"{repo_hash} 0 0 0 0\n"

        with open(filename, 'w') as f:
            f.writelines(cache_comment)
            f.writelines(data)

        loc_add = loc_del = 0
        for line in data:
            loc_add += int(line.split()[3])
            loc_del += int(line.split()[4])
        return [loc_add, loc_del, loc_add - loc_del, cached]

    @classmethod
    def flush_cache(cls, edges, filename, comment_size):
        with open(filename, 'r') as f:
            data = f.readlines()[:comment_size] if comment_size > 0 else []
        with open(filename, 'w') as f:
            f.writelines(data)
            for node in edges:
                f.write(hashlib.sha256(
                    node['node']['nameWithOwner'].encode()).hexdigest() + ' 0 0 0 0\n')

    @classmethod
    def recursive_loc(cls, owner, repo_name, data, cache_comment, addition_total=0, deletion_total=0, my_commits=0, cursor=None):
        cls.query_count_inc('recursive_loc')
        query = '''query ($repo_name: String!, $owner: String!, $cursor: String) {
            repository(name: $repo_name, owner: $owner) {
                defaultBranchRef {target {... on Commit {history(first: 100, after: $cursor) {totalCount edges {node {committedDate author{user{id}} deletions additions}} pageInfo {endCursor hasNextPage}}}}}}}'''
        variables = {'repo_name': repo_name, 'owner': owner, 'cursor': cursor}
        request = requests.post('https://api.github.com/graphql',
                                json={'query': query, 'variables': variables}, headers=cls.HEADERS)
        if request.status_code == 200:
            history = request.json()[
                'data']['repository']['defaultBranchRef']['target']['history']
            for node in history['edges']:
                user = node['node']['author']['user']
                if user and user.get('id') == cls.OWNER_ID:
                    my_commits += 1
                    addition_total += node['node']['additions']
                    deletion_total += node['node']['deletions']
            if not history['pageInfo']['hasNextPage']:
                return addition_total, deletion_total, my_commits
            return cls.recursive_loc(owner, repo_name, data, cache_comment, addition_total, deletion_total, my_commits, history['pageInfo']['endCursor'])
        raise Exception('recursive_loc failed',
                        request.status_code, request.text)

    @classmethod
    def commit_counter(cls, comment_size):
        filename = f'cache/{hashlib.sha256(cls.USER_NAME.encode()).hexdigest()}.txt'
        with open(filename, 'r') as f:
            data = f.readlines()
        data = data[comment_size:]
        return sum(int(line.split()[2]) for line in data)

    @classmethod
    def get_dots(cls, total_len, text_len):
        just_len = max(0, total_len - text_len)
        return '.' * just_len if just_len > 0 else ''

    @classmethod
    def get_user_dots(cls, key, value):
        just_len = max(0, 55 - len(key) - len(str(value)))
        return '.' * just_len if just_len > 0 else ''

    @classmethod
    def calc_age(cls, birth_str):
        try:
            b = datetime.strptime(birth_str, '%d-%m-%Y')
        except ValueError:
            try:
                b = datetime.strptime(birth_str, '%d-%m-%Y')
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
    def read_gif_base64(cls, gif_path):
        try:
            with open(gif_path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except FileNotFoundError:
            return ""

    @classmethod
    def build_svg(cls, mode, commit_data, star_data, repo_data, contrib_data, follower_data, loc_data):
        age_str = cls.calc_age(cls.BIRTHDAY)
        commit_str = f"{commit_data:,}"
        star_str = f"{star_data:,}"
        repo_str = f"{repo_data:,}"
        contrib_str = f"{contrib_data:,}"
        follower_str = f"{follower_data:,}"
        loc_str = f"{loc_data[2]:,}"
        loc_add_str = f"{loc_data[0]:,}"
        loc_del_str = f"{loc_data[1]:,}"

        gif_b64 = cls.read_gif_base64('assets/coder-lego.gif')
        gif_data = f"data:image/gif;base64,{gif_b64}" if gif_b64 else ""

        commit_dots = cls.get_dots(20, len(commit_str))
        star_dots = cls.get_dots(12, len(star_str))
        repo_dots = cls.get_dots(5, len(repo_str))
        follower_dots = cls.get_dots(9, len(follower_str))
        loc_dots = cls.get_dots(8, len(loc_str))
        loc_del_dots = cls.get_dots(6, len(loc_del_str))

        os_dots = cls.get_user_dots("OS", cls.OS)
        age_dots = cls.get_user_dots("Uptime", age_str)
        host_dots = cls.get_user_dots("Host", cls.HOST)
        kernel_dots = cls.get_user_dots("Kernel", cls.KERNEL)
        ide_dots = cls.get_user_dots("IDE", cls.IDE)
        lang_prog_dots = cls.get_user_dots(
            "Languages.Programming", cls.LANGUAGES_PROG)
        lang_comp_dots = cls.get_user_dots(
            "Languages.Computer", cls.LANGUAGES_COMP)
        lang_real_dots = cls.get_user_dots(
            "Languages.Real", cls.LANGUAGES_REAL)
        email_dots = cls.get_user_dots("Email.Personal", cls.EMAIL)
        website_dots = cls.get_user_dots("Website.Personal", cls.WEBSITE)
        linkedin_dots = cls.get_user_dots("LinkedIn", cls.LINKEDIN)
        twitter_dots = cls.get_user_dots("X", cls.TWITTER)
        discord_dots = cls.get_user_dots("Discord", cls.DISCORD)
        instagram_dots = cls.get_user_dots("Instagram", cls.INSTAGRAM)
        hobbies_hardware_dots = cls.get_user_dots("Hobbies.Hardware", cls.Hobbies_Hardware)
        hobbies_software_dots = cls.get_user_dots("Hobbies.Software", cls.Hobbies_Software)
        box_height = 550
        
        if mode == "dark":
            bg_fill = "#161b22"
            text_fill = "#c9d1d9"
            key_fill = "#ffa657"
            value_fill = "#a5d6ff"
            add_fill = "#3fb950"
            del_fill = "#f85149"
            cc_fill = "#616e7f"
            rect_fill = "#161b22"
        else:
            bg_fill = "#f6f8fa"
            text_fill = "#24292f"
            key_fill = "#953800"
            value_fill = "#0a3069"
            add_fill = "#1a7f37"
            del_fill = "#cf222e"
            cc_fill = "#c2cfde"
            rect_fill = "#f6f8fa"

        svg_parts = [
            f'<?xml version=\'1.0\' encoding=\'UTF-8\'?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" font-family="ConsolasFallback,Consolas,monospace" width="985px" height="{box_height}px" font-size="16px">',
            '<style>',
            '@font-face {',
            '  src: local(\'Consolas\'), local(\'Consolas Bold\');',
            "  font-family: 'ConsolasFallback';",
            "  font-display: swap;",
            "  -webkit-size-adjust: 109%;",
            "  size-adjust: 109%;",
            '}',
            f'.key {{fill: {key_fill};}}',
            f'.value {{fill: {value_fill};}}',
            f'.addColor {{fill: {add_fill};}}',
            f'.delColor {{fill: {del_fill};}}',
            f'.cc {{fill: {cc_fill};}}',
            'text, tspan {white-space: pre;}',
            '</style>',
            f'<rect width="985px" height="{box_height}px" fill="{rect_fill}" rx="15" />',
            f'<image x="15" y="30" width="350" height="480" href="{gif_data}" />',
            f'<text x="390"  y="30" fill="{text_fill}">',
            f'  <tspan x="390"  y="30">{cls.USER_NAME}</tspan> -———————————————————————————————————————————-—-',
            f'  <tspan x="390"  y="50" class="cc">. </tspan><tspan class="key">OS</tspan>:<tspan class="cc">{os_dots}</tspan><tspan class="value">{cls.OS}</tspan>',
            f'  <tspan x="390"  y="70" class="cc">. </tspan><tspan class="key">Uptime</tspan>:<tspan class="cc">{age_dots}</tspan><tspan class="value">{age_str}</tspan>',
            f'  <tspan x="390"  y="90" class="cc">. </tspan><tspan class="key">Host</tspan>:<tspan class="cc">{host_dots}</tspan><tspan class="value">{cls.HOST}</tspan>',
            f'  <tspan x="390"  y="110" class="cc">. </tspan><tspan class="key">Kernel</tspan>:<tspan class="cc">{kernel_dots}</tspan><tspan class="value">{cls.KERNEL}</tspan>',
            f'  <tspan x="390"  y="130" class="cc">. </tspan><tspan class="key">IDE</tspan>:<tspan class="cc">{ide_dots}</tspan><tspan class="value">{cls.IDE}</tspan>',
            f'  <tspan x="390"  y="170" class="cc">. </tspan><tspan class="key">Languages</tspan>.<tspan class="key">Programming</tspan>:<tspan class="cc">{lang_prog_dots}</tspan><tspan class="value">{cls.LANGUAGES_PROG}</tspan>',
            f'  <tspan x="390"  y="190" class="cc">. </tspan><tspan class="key">Languages</tspan>.<tspan class="key">Computer</tspan>:<tspan class="cc">{lang_comp_dots}</tspan><tspan class="value">{cls.LANGUAGES_COMP}</tspan>',
            f'  <tspan x="390"  y="210" class="cc">. </tspan><tspan class="key">Languages</tspan>.<tspan class="key">Real</tspan>:<tspan class="cc">{lang_real_dots}</tspan><tspan class="value">{cls.LANGUAGES_REAL}</tspan>',
            f'  <tspan x="390"  y="250" class="cc">. </tspan><tspan class="key">Hobbies</tspan>.<tspan class="key">Software</tspan>:<tspan class="cc">{hobbies_software_dots}</tspan><tspan class="value">{cls.Hobbies_Software}</tspan>',
            f'  <tspan x="390"  y="270" class="cc">. </tspan><tspan class="key">Hobbies</tspan>.<tspan class="key">Hardware</tspan>:<tspan class="cc">{hobbies_hardware_dots}</tspan><tspan class="value">{cls.Hobbies_Hardware}</tspan>',
            f'  <tspan x="390"  y="310">- Contact</tspan> -———————————————————————————————————————————-—---',
            f'  <tspan x="390"  y="330" class="cc">. </tspan><tspan class="key">Email</tspan>.<tspan class="key">Personal</tspan>:<tspan class="cc">{email_dots}</tspan><tspan class="value">{cls.EMAIL}</tspan>',
            f'  <tspan x="390"  y="350" class="cc">. </tspan><tspan class="key">Website</tspan>.<tspan class="key">Personal</tspan>:<tspan class="cc">{website_dots}</tspan><tspan class="value">{cls.WEBSITE}</tspan>',
            f'  <tspan x="390"  y="370" class="cc">. </tspan><tspan class="key">LinkedIn</tspan>:<tspan class="cc">{linkedin_dots}</tspan><tspan class="value">{cls.LINKEDIN}</tspan>',
            f'  <tspan x="390"  y="390" class="cc">. </tspan><tspan class="key">X</tspan>:<tspan class="cc">{twitter_dots}</tspan><tspan class="value">{cls.TWITTER}</tspan>',
            f'  <tspan x="390"  y="410" class="cc">. </tspan><tspan class="key">Discord</tspan>:<tspan class="cc">{discord_dots}</tspan><tspan class="value">{cls.DISCORD}</tspan>',
            f'  <tspan x="390"  y="430" class="cc">. </tspan><tspan class="key">Instagram</tspan>:<tspan class="cc">{instagram_dots}</tspan><tspan class="value">{cls.INSTAGRAM}</tspan>',
            f'  <tspan x="390"  y="470">- GitHub Stats</tspan> -—————————————————————————————————————————-—',
            f'  <tspan x="390"  y="490" class="cc">. </tspan><tspan class="key">Repos</tspan>:<tspan class="cc">{repo_dots}</tspan><tspan class="value">{repo_str}</tspan> {{<tspan class="key">Contributed</tspan>: <tspan class="value">{contrib_str}</tspan>}} | <tspan class="key">Stars</tspan>:<tspan class="cc">{star_dots}</tspan><tspan class="value">{star_str}</tspan>',
            f'  <tspan x="390"  y="510" class="cc">. </tspan><tspan class="key">Commmits</tspan>:<tspan class="cc">{commit_dots}</tspan><tspan class="value">{commit_str}</tspan> | <tspan class="key">Followers</tspan>:<tspan class="cc">{follower_dots}</tspan><tspan class="value">{follower_str}</tspan>',
            f'  <tspan x="390"  y="530" class="cc">. </tspan><tspan class="key">Lines of Code on GitHub</tspan>:<tspan class="cc">{loc_dots}</tspan><tspan class="value">{loc_str}</tspan>',
            f' (<tspan class="addColor">{loc_add_str}</tspan><tspan class="addColor">++</tspan>, <tspan class="delColor">{loc_del_str}</tspan><tspan class="delColor">--</tspan>) </text>',
            '</svg>'
        ]

        return '\n'.join(svg_parts)

    @classmethod
    def generate_svgs(cls, commit_data, star_data, repo_data, contrib_data, follower_data, loc_data):
        os.makedirs('assets', exist_ok=True)

        dark_svg = cls.build_svg(
            "dark", commit_data, star_data, repo_data, contrib_data, follower_data, loc_data)
        light_svg = cls.build_svg(
            "light", commit_data, star_data, repo_data, contrib_data, follower_data, loc_data)

        with open('assets/dark_mode.svg', 'w', encoding='utf-8') as f:
            f.write(dark_svg)
        with open('assets/light_mode.svg', 'w', encoding='utf-8') as f:
            f.write(light_svg)

    @classmethod
    def update_readme(cls, dark_svg_path, light_svg_path, readme_path='README.md'):
        import re
        with open(dark_svg_path, 'rb') as f:
            dark_b64 = base64.b64encode(f.read()).decode('utf-8')
        with open(light_svg_path, 'rb') as f:
            light_b64 = base64.b64encode(f.read()).decode('utf-8')

        dark_data_uri = f"data:image/svg+xml;base64,{dark_b64}"
        light_data_uri = f"data:image/svg+xml;base64,{light_b64}"

        with open(readme_path, 'r') as f:
            readme_content = f.read()

        readme_content = re.sub(
            r'<source media="\(prefers-color-scheme: dark\)" srcset="[^"]+">',
            f'<source media="(prefers-color-scheme: dark)" srcset="{dark_data_uri}">',
            readme_content
        )
        readme_content = re.sub(
            r'<img alt="([^"]+)" src="[^"]+">',
            f'<img alt="\\1" src="{light_data_uri}">',
            readme_content
        )

        with open(readme_path, 'w') as f:
            f.write(readme_content)


if __name__ == '__main__':
    if os.path.exists('assets'):
        for f in os.listdir('assets'):
            if f.endswith('.svg'):
                try:
                    os.remove(f'assets/{f}')
                except FileNotFoundError:
                    pass

    total_loc = UserStats.loc_query(
        ['OWNER', 'COLLABORATOR', 'ORGANIZATION_MEMBER'], 7)
    commit_data = UserStats.commit_counter(7)
    star_data = UserStats.graph_repos_stars('stars', ['OWNER'])
    repo_data = UserStats.graph_repos_stars('repos', ['OWNER'])
    contrib_data = UserStats.graph_repos_stars(
        'repos', ['OWNER', 'COLLABORATOR', 'ORGANIZATION_MEMBER'])
    follower_data = UserStats.follower_getter()

    UserStats.generate_svgs(commit_data, star_data,
                            repo_data, contrib_data, follower_data, total_loc)
    # UserStats.update_readme('assets/dark_mode.svg', 'assets/light_mode.svg')
