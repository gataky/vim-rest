import time

import os
import yaml
import curlify
import neovim
import requests
import shlex
import urllib.parse as urllib

OUTPUT_BUFFER_NAME = '[request_output]'
WORKSPACE_DIR = os.path.expanduser('~/.local/share/nvim_rc')
WORKSPACE_GLOBAL = 'nvim_rc_global.yaml'

PREFIX = ""

LIST_WORKSPACES  = f"{PREFIX}ListWorkspaces"
NEW_WORKSPACE    = f"{PREFIX}NewWorkspace"
EDIT_WORKSPACE   = f"{PREFIX}EditWorkspace"
SET_WORKSPACE    = f"{PREFIX}SetWorkspace"

LIST_REQUESTS  = f"{PREFIX}ListRequests"
NEW_REQUEST    = f"{PREFIX}NewRequest"
EDIT_REQUEST   = f"{PREFIX}EditRequest"
SEND_REQUEST   = f"{PREFIX}SendRequest"

base_yaml = """url:
method:
headers:
data:
"""


@neovim.plugin
class Main:
    def __init__(self, vim):
        self.vim = vim
        self._output_buffer_number = None
        self.workspace = 'foo'

    @neovim.command(LIST_WORKSPACES, bang=True)
    def list_workspaces(self, *args):
        run_args = self._fzf_run_args(f'ls {WORKSPACE_DIR}', SET_WORKSPACE)
        self.vim.command(f"call fzf#run({run_args})")

    @neovim.command(NEW_WORKSPACE, nargs=1, bang=True)
    def new_workspaces(self, *args):
        name = args[0][0]
        path = os.path.join(WORKSPACE_DIR, name)
        os.makedirs(path, exist_ok=True)
        glbl = os.path.join(WORKSPACE_DIR, name, WORKSPACE_GLOBAL)
        with open(glbl, 'w') as f:
            f.write(base_yaml)
        self.workspace = name
        self.edit_workspace()

    @neovim.command(EDIT_WORKSPACE, bang=True)
    def edit_workspace(self, *args):
        glbl = os.path.join(WORKSPACE_DIR, self.workspace, WORKSPACE_GLOBAL)
        self.vim.command(f"edit {glbl}")

    @neovim.command(SET_WORKSPACE, nargs=1)
    def set_workspace(self, workspace):
        self.workspace = workspace.pop()

    @neovim.command(LIST_REQUESTS, bang=True)
    def list_workspace(self, *args):
        if not self.workspace:
            self.vim.command('echom "No workspace set"')
            return
        path = os.path.join(WORKSPACE_DIR, self.workspace)
        run_args = self._fzf_run_args(f'ls {path}', EDIT_REQUEST)
        self.vim.command(f"call fzf#run({run_args})")

    @neovim.command(NEW_REQUEST, nargs=1, bang=True)
    def new_request(self, *args):
        name = args[0][0]
        path = os.path.join(WORKSPACE_DIR, self.workspace, name)
        self.vim.command(f"edit {path}.yaml")

    @neovim.command(EDIT_REQUEST, nargs=1, bang=True)
    def edit_request(self, *args):
        name = args[0][0]
        path = os.path.join(WORKSPACE_DIR, self.workspace, name)
        self.vim.command(f'edit {path}')

    @neovim.command(SEND_REQUEST)
    def call(self, *args):

        data = self._load_yaml()
        r = requests.request(**data)

        data = self._format_curl_request(r.request)
        data.append('')

        headers = self._format_response_headers(r)
        data.extend(headers)
        data.append('')

        data.extend(r.text.split('\n'))

        buffer = self._get_output_buffer()
        buffer[:] = data

    def _find_output_buffer(self):
        try:
            return self.vim.buffers[self._output_buffer_number]
        except KeyError:
            for buffer in self.vim.buffers:
                if OUTPUT_BUFFER_NAME in buffer.name:
                    self._output_buffer_number = buffer.number
                    return self.vim.buffers[buffer.number]
            return None

    def _create_output_buffer(self):
        self.vim.command(f'new {OUTPUT_BUFFER_NAME} | setlocal nobuflisted buftype=nofile bufhidden=wipe noswapfile')
        return self._find_output_buffer()

    def _get_output_buffer(self):
        buffer = self._find_output_buffer()
        if buffer:
            return buffer
        return self._create_output_buffer()

    @staticmethod
    def _format_curl_request(request):
        curl = curlify.to_curl(request)
        curl_args: list[str] = shlex.split(curl)

        lines = [curl_args[0] + " \\"]
        line = []
        for arg in curl_args[1:-1]:
            if arg.startswith('-'):
                line.append(arg)
            else:
                line.append(arg)
                lines.append(" ".join(line) + " \\")
                line = []
        lines.append(curl_args[-1])
        return lines

    @staticmethod
    def _format_response_headers(response):
        lines = []
        for k, v in response.headers.items():
            lines.append(f'{k}: {v}')
        return lines

    @staticmethod
    def _fzf_run_args(source, sink):
        return str({
            'source': source,
            'sink': sink
        })

    def _load_yaml(self):

        gp = os.path.join(WORKSPACE_DIR, self.workspace, WORKSPACE_GLOBAL)
        g = {}
        try:
            os.stat(gp)
        except FileExistsError as e:
            g = {}
        else:
            with open(gp) as f:
                g = yaml.safe_load(f)

        if WORKSPACE_GLOBAL in self.vim.current.buffer.name:
            f = {}
        else:
            f = "\n".join(self.vim.current.buffer)
            f = yaml.safe_load(f)

        base_url = g.pop('url', '')
        path_url = f.pop('url', '')
        url = urllib.urljoin(base_url, path_url)
        self.vim.command(f"echom '{base_url}'")

        data = {**g, **f}
        data['url'] = url

        if 'method' not in data:
            data['method'] = 'GET'

        return data
