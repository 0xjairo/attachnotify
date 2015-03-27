#!/usr/bin/python -u
from argparse import ArgumentParser
from subprocess import Popen, PIPE
import os
import yaml
try:
    import psutil
except ImportError:
    raise SystemExit(('Please install psutil '
                      'i.e., pip install psutil'))

## if uid != 0 (root/sudo)
#if os.getuid():
#    raise SystemExit(
#        ('Error: strace needs root permissions. '
#         'Please run as root'))


def call(cmd):
    # print 'Command:', ' '.join(cmd)
    try:
        p = Popen(cmd,
                  shell=False,
                  bufsize=False,
                  stdin=PIPE,
                  stdout=PIPE,
                  stderr=PIPE)
    except OSError:
        err = 'Error: Command not found:\n  {}'.format(cmd[0])
        return '', err, -1

    stdout, stderr = p.communicate()
    returncode = p.returncode if not None else 0
    return stdout, stderr, returncode


def run_notifier(notifier, pdata):
    title = '{}'.format(pdata['name'])
    msg = ['strace:{}'.format(pdata['exitmsg']),
           'cmd:{}'.format(pdata['cmdline']),
           'cwd:{}'.format(pdata['cwd'])
           ]

    # build command
    cmd = [notifier['exec']]

    try:
        cmd.append(notifier['message'].format(msg))
    except KeyError:
        # Notifier does not specify messages
        pass

    try:
        cmd.append(notifier['title'].format(title))
    except KeyError:
        pass

    try:
        cmd.append(notifier['priority'].format(
            pdata.get('priority', 0)))
    except KeyError:
        pass

    # try adding arguments for 'onerror' and
    # 'onsuccess'
    if pdata.get('retcode', 0):
        try:
            cmd.append(notifier['onerror'])
        except KeyError:
            pass
    else:
        try:
            cmd.append(notifier['onsuccess'])
        except KeyError:
            pass

    try:
        cmd.append(notifier['args'])
    except KeyError:
        pass

    print 'Notifier:', ' '.join(cmd)
    stdout, stderr, retcode = call(cmd)

    if stdout:
        print stdout
    if stderr:
        print stderr


def main():

    parser = ArgumentParser(
        description=('Use strace to attach to a running '
                     'process, specifed by name, and send '
                     'exit code to user with pushover'))

    parser.add_argument('pid', type=int, help='PID of program to attach to')
    parser.add_argument('-c', '--config', type=str,
                        help='Path configuration file')

    args, unknown = parser.parse_known_args()

    if args.config and not os.path.isfile(args.config):
        raise SystemExit('Error: Config file specified does not exist')
    else:
        # try ~/.attachnotifyrc
        args.config = os.path.expanduser('~/.attachnotifyrc')
        if not os.path.isfile(args.config):
            raise SystemExit('Error: Config file specified does not exist')

    cfg = yaml.load(open(args.config, 'r'))
    try:
        notifiers = cfg['notifiers']
        # Expand '~' with /home/user
        for notifier in notifiers:
            for k, v in notifier.iteritems():
                expanded = os.path.expanduser(v)
                notifier[k] = expanded

    except KeyError:
        raise SystemExit('Error: Missing notifiers key in configuration file')

    # grab name of process
    p = psutil.Process(args.pid)
    pdata = {
        'cwd': p.cwd(),
        'name': p.name(),
        'cmdline': ' '.join(p.cmdline())}

    # print info
    print 'Attaching strace to pid {}({})'.format(args.pid, pdata['name'])
    print ' '*2 + 'cmd: {}'.format(pdata['cmdline'])
    print ' '*2 + 'cwd: {}'.format(pdata['cwd'])

    # strace command
    strace = 'sudo strace -e none -e exit_group -p {}'.format(args.pid)
    stdout, stderr, retcode = call(strace.split())

    # store return code
    pdata['retcode'] = retcode

    # look at stderr for the exit code
    for line in stderr.split('\n'):
        if line.startswith('+++'):
            pdata['exitmsg'] = line

            for n in notifiers:
                run_notifier(n, pdata)
            break


if __name__ == '__main__':
    main()
