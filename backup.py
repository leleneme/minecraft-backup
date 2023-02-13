import argparse
import os
import time
import subprocess
import sys

from mcrcon import MCRcon
import lockfile

MAX_BACKUPS = 10
MSG_BACKUP_FAILED = 'Automatic server backup failed. Contact the server administrator'
MSG_BACKUP_STARTED = 'Automatic backup started...'
MSG_BACKUP_SUCCESS = 'Automatic backup created and archived successfully'

disable_messages = False


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def main():
    parser = argparse.ArgumentParser(
        prog=f'{os.path.basename(__file__)}',
        description='Connects to RCON and automatically backups the Minecraft World'
    )

    parser.add_argument('--host', dest='host', required=True)
    parser.add_argument('--port', dest='port', type=int,
                        required=False, default=25575)
    parser.add_argument('--password', dest='password', required=True)
    parser.add_argument('--world', dest='world_path', required=True)
    parser.add_argument('--dest', dest='backup_folder', required=True)
    parser.add_argument('--disable-messages', dest='disable_messages',
                        required=False, action='store_true')

    args = parser.parse_args()

    global disable_messages
    disable_messages = args.disable_messages

    try:
        with MCRcon() as rcon:
            if not rcon.connect(args.host, args.port):
                eprint('Invalid host and/or port number')
                exit(1)

            if not rcon.login(args.password):
                eprint('Invalid RCON credentials')
                rcon.close()
                exit(1)

            rcon.send_command('list')

            print('Starting backup...')
            run_backup(rcon, args.world_path, args.backup_folder)
    except Exception as ex:
        eprint(f'An exception was raised: {ex}')


def send_message(rcon: MCRcon, message: str, color: str = 'light_purple'):
    if not disable_messages:
        command = f"""/tellraw @a ["",{{"text":"[BACKUP] ","bold":true,"color":"{color}"}},{{"text":"{message}","color":"{color}"}}]"""
        rcon.send_command(command)


def create_backup(world_path: str, backup_path: str) -> bool:
    timestamp = int(time.time())
    archive_name = f'{timestamp}.tar.zst'
    final_backup_path = os.path.join(backup_path, archive_name)

    command = ['tar', '-I', 'zstd', '-cf',
               final_backup_path, '-C', world_path, '.']

    print(f'Running: {" ".join(command)}')

    result = subprocess.run(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    stderr = result.stderr.decode("utf-8")

    if len(stderr) > 0:
        eprint(f'{stderr}')

    return result.returncode == 0


def clear_old_backups(backup_path: str):
    files = [f for f in os.listdir(backup_path) if f.endswith('.tar.zst')]
    files.sort(reverse=True)

    to_keep = files[0:MAX_BACKUPS]
    to_remove = [f for f in files if f not in to_keep]

    print(f'Found {len(to_remove)} backups to remove')

    for file in to_remove:
        os.remove(os.path.join(backup_path, file))


def run_backup(rcon: MCRcon, world_path: str, backup_path: str) -> bool:
    try:
        send_message(rcon, MSG_BACKUP_STARTED)

        rcon.send_command('save-off')
        rcon.send_command('save-all')

        print('Waiting to ensure everything is written to disk')
        time.sleep(5)

        backup_result = create_backup(world_path, backup_path)

        if backup_result:
            send_message(rcon, MSG_BACKUP_SUCCESS)
            clear_old_backups(backup_path)
        else:
            send_message(rcon, MSG_BACKUP_FAILED, color='red')
    except Exception as ex:
        eprint(f'An exception was raised during backup: {ex}')
        send_message(rcon, MSG_BACKUP_FAILED, color='red')
    finally:
        rcon.send_command('save-all')
        rcon.send_command('save-on')

    return True


if __name__ == '__main__':
    if lockfile.exists():
        eprint("Lock file exists! Either the program is already running or it's lock file wasn't properly released")
        exit(1)

    try:
        lockfile.create()
    except Exception as ex:
        eprint('Could not create lock file, exiting...')
        exit(1)

    try:
        main()
    finally:
        lockfile.delete()
