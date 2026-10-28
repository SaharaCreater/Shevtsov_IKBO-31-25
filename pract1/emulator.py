import os
import sys
import hashlib
import getpass
import socket
from pathlib import Path


class VirtualFileSystem:

    def __init__(self, physical_path: str):
        self.physical_root = Path(physical_path).resolve()
        if not self.physical_root.exists() or not self.physical_root.is_dir():
            raise ValueError(f"Путь VFS не существует или не является директорией: {physical_path}")

        self.vfs_data = {}
        self.sha256_hash = ""
        self._load_and_hash()

    def _load_and_hash(self):
        sha256 = hashlib.sha256()
        for root, dirs, files in os.walk(self.physical_root):
            rel_root = Path(root).relative_to(self.physical_root)
            rel_root_str = "" if rel_root == Path(".") else str(rel_root).replace("\\", "/")

            if rel_root_str:
                self.vfs_data[rel_root_str] = {'type': 'dir'}

            for file in files:
                file_path = Path(root) / file
                rel_file_path = rel_root / file
                rel_file_str = str(rel_file_path).replace("\\", "/")

                try:
                    with open(file_path, "rb") as f:
                        content = f.read()

                    sha256.update(rel_file_str.encode('utf-8'))
                    sha256.update(content)

                    self.vfs_data[rel_file_str] = {
                        'type': 'file',
                        'content': content
                    }
                except Exception as e:
                    print(f"Предупреждение: не удалось прочитать файл {file_path}: {e}")

        self.vfs_data[""] = {'type': 'dir'}
        self.sha256_hash = sha256.hexdigest()

    def get_info(self):
        return {
            "name": self.physical_root.name,
            "hash": self.sha256_hash
        }


class ShellEmulator:
    def __init__(self, vfs_path: str, startup_script: str = None):
        print("=== Инициализация эмулятора (Конфигурация) ===")
        print(f"Путь к физическому расположению VFS: {vfs_path}")
        print(f"Путь к стартовому скрипту: {startup_script}")
        print("==============================================\n")

        try:
            self.vfs = VirtualFileSystem(vfs_path)
        except Exception as e:
            print(f"Ошибка инициализации VFS: {e}")
            sys.exit(1)

        self.current_dir = ""
        self.username = getpass.getuser()
        self.hostname = socket.gethostname()
        self.running = True
        self.startup_script = startup_script

    def get_prompt(self):
        display_dir = "~" if not self.current_dir else f"~/{self.current_dir}"
        return f"{self.username}@{self.hostname}:{display_dir}$ "

    def resolve_path(self, path_str: str) -> str:
        if not path_str or path_str == ".":
            return self.current_dir

        if path_str.startswith("/"):
            parts = list(Path(path_str).parts[1:])
        else:
            base_parts = list(Path(self.current_dir).parts) if self.current_dir else []
            parts = base_parts + list(Path(path_str).parts)

        resolved = []
        for p in parts:
            if p == "..":
                if resolved:
                    resolved.pop()
            elif p != ".":
                resolved.append(p)

        return "/".join(resolved)

    def execute_command(self, cmd_line: str):
        cmd_line = cmd_line.strip()
        if not cmd_line or cmd_line.startswith("#"):
            return

        for key, val in os.environ.items():
            cmd_line = cmd_line.replace(f"${key}", val)
        cmd_line = cmd_line.replace("$HOME", os.path.expanduser("~"))
        cmd_line = cmd_line.replace("$USER", self.username)

        tokens = cmd_line.split()
        if not tokens:
            return

        cmd = tokens[0]
        args = tokens[1:]

        if cmd == "exit":
            self.running = False
        elif cmd == "vfs-info":
            info = self.vfs.get_info()
            print(f"VFS Name: {info['name']}")
            print(f"SHA-256 Hash: {info['hash']}")
        elif cmd == "echo":
            print(" ".join(args))
        elif cmd == "ls":
            print(f"ls: имя команды, аргументы: {args} (текущая директория VFS: ~/{self.current_dir})")
        elif cmd == "cd":
            print(f"cd: имя команды, аргументы: {args}")
            if args:
                target = self.resolve_path(args[0])
                if target == "" or target in self.vfs.vfs_data:
                    self.current_dir = target
                else:
                    print(f"cd: no such file or directory: {args[0]}")
        else:
            print(f"zsh: command not found: {cmd}")

    def run(self):
        if self.startup_script and os.path.exists(self.startup_script):
            print(f"--- Запуск стартового скрипта: {self.startup_script} ---")
            with open(self.startup_script, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped:
                        print(self.get_prompt() + stripped)
                        try:
                            self.execute_command(stripped)
                        except Exception as e:
                            print(f"Ошибка выполнения строки: {e} (пропущено)")
            print("--- Конец выполнения скрипта ---\n")

        while self.running:
            try:
                cmd_line = input(self.get_prompt())
                self.execute_command(cmd_line)
            except (KeyboardInterrupt, EOFError):
                print()
                break


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="UNIX Shell Emulator (Stages 1-3)")
    parser.add_argument("--vfs", required=True, help="Путь к физическому расположению VFS")
    parser.add_argument("--script", help="Путь к стартовому скрипту")

    parsed_args = parser.parse_args()

    emulator = ShellEmulator(vfs_path=parsed_args.vfs, startup_script=parsed_args.script)
    emulator.run()