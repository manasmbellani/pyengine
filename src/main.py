#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys

import requests
import yaml

DESCRIPTION = "Script to parse checks files, and execute commands"

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36"

class CustomFormatter(argparse.RawTextHelpFormatter, argparse.ArgumentDefaultsHelpFormatter):
    pass

def error(msg):
    """
    Print error

    Args:
        msg (str): Error message

    Returns:
        str: Error string
    """
    e = "[*] " + msg
    print(e)
    return e

def debug(msg):
    """
    Print debug message

    Args:
        err (str): Debug message

    Returns:
        str: Message string
    """
    m = "[*] " + msg
    print(m)
    return m

def warning(msg):
    """
    Print warning message

    Args:
        err (str): Debug message

    Returns:
        str: Message string
    """
    m = "[!] " + msg
    print(m)
    return m

def notes(msg):
    """
    Print Notes aka manual actions to perform

    Args:
        msg (str/list): Notes message(s)

    Returns:
        str: Message string
    """
    msgs_txt = []
    if isinstance(msg, str):
        msgs = [msg]
    else:
        msgs = msgs
    
    for msg in msgs:
        m = "[!] " + msg
        print(m)
        msgs_txt.append(m)
    
    return "\n".join(msgs_txt)

def task_cmd(cmds, conf):
    """Execute command(s)

    Args:
        cmds (str/list): Shell command(s) to execute
        conf (dict): Configuration with settings to substitute in cmd

    Returns:
        (bool, str): Boolean on whether the command was executed AND output
    """
    was_cmd_successful = False
    out_text = ""
    if isinstance(cmds, str):
        cmds = [cmds]
    
    # Join all commands together to execute in the shell
    cmd_to_exec = "; ".join(cmds)

    for c in cmds:
        try:
            debug(f"Executing command: {cmd_to_exec}...")
            p = subprocess.Popen(sub_conf.format(cmd_to_exec, conf), shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            out, __ = p.communicate()
            out_text = out.decode().strip()
            was_cmd_successful = True
        except Exception as e:
            error(f"Error executing command: {c}. Error: {e.__class__}, {e}")
        
    return was_cmd_successful, out_text

def task_web_request(url, conf, data={}, user_headers={}, user_agent=USER_AGENT):
    """Make a GET/POST request

    Args:
        url(str): URL to call
        conf (dict): Configuration to substitute in cmd
        data(dict): POST Data 
        user_headers(dict): Headers to send
        user_agent(str): Default user agent string

    Returns:
        (bool, int, str): Boolean on whether the request was successful
    """
    was_request_successful = False
    status_code = 0
    resp_text = ""
    try:

        url_sub = sub_conf(url, conf)

        headers = {}
        headers["User-Agent"] = user_agent
        if user_headers:
            user_headers_sub = {}
            for hk, hv in user_headers.items():
                k = sub_conf(hk, conf)
                v = sub_conf(hv, conf)
                user_headers_sub[k] = v
            headers.update(user_headers_sub)
        if data:
            data_sub = {}
            for dk, dv in data.items():
                dk = sub_conf(dk)
                dv = sub_conf(dv)
                data_sub[dk] = dv
            debug(f"Making POST request to URL: {url}...")
            r = requests.post(url_sub, data=data_sub, headers=headers)
        else:
            debug(f"Making GET request to URL: {url}...")
            r = requests.get(url_sub, headers=headers)

        status_code = r.status_code
        resp_text = r.text
        was_request_successful = True

    except Exception as e:
        error(f"Error making web request to URL: {url}. Error: {e.__class__}, {e}")
    
    return was_request_successful, status_code, resp_text

def prepare_conf_dict(targets, settings):
    """Prepare a list of configuration combining the inputs from user
    to substitute in commands

    Args:
        targets (str): list of targets to use (comma-separated)
        settings (dict): list of additional settings to use

    Returns:
        list: List of targets/settings to use on the engine
    """
    conf_list = []
    
    for t in targets:
        conf = {"target": t.strip()}
        conf.update(settings)
        conf_list.append(conf)

    return conf_list

def check_out(r, inp):
    """Use regex to check input str

    Args:
        r: Regex to check
        in: Output

    Returns:
        bool: Check output
    """
    if not isinstance(inp, str):
        inp_str = str(inp)
    else:
        inp_str = inp

    match = False
    m = re.search(r, inp_str, re.I)
    if m:
        match = True
    return match

def sub_conf(s, conf):
    """Substitute values in str using configuration

    Args:
        s (str): Substitue values in str/list
        conf (dict): Configuration to substitute

    Returns:
        str: Substituted str with configuration
    """
    return s.format(**conf)

def write_to_outfile(outfile, ls):
    """Write output to a file
    
    Args:
        outfile (str): Output file to write content
        ls (str): Lines to write to file
    """
    with open(outfile, "w+") as f:
        if isinstance(ls, str):
            ls = [ls]
        for l in ls:
            f.write(l.strip() + "\n")

def parse_checks_files(checks_files, regex):
    """Parse the checks files

    Args:
        checks_file (str): Checks files
        regex (str): Regex specifying which checks files to parse/execute

    Returns:
        dict: Checks file configuration for each file parsed
    """
    all_conf = {}
    checks_fs = checks_files.split(",")

    for check_f in checks_fs:
        if os.path.isfile(check_f.strip()):
            with open(check_f.strip(), "r") as fo:
                try:
                    yaml_conf = yaml.safe_load(fo)
                    all_conf[check_f] = yaml_conf
                except Exception as e:
                    error(f"Error parsing file: {check_f}. Error: {e.__class__}, {e}")

        elif os.path.isdir(check_f.strip()):
            for dir, _, files in os.walk(check_f.strip()):
                for f in files:
                    p = os.path.join(dir, f)
                    with open(p, "r") as fo:
                        try:
                            yaml_conf = yaml.safe_load(fo)
                            all_conf[p] = (yaml_conf)
                        except Exception as e:
                            error(f"Error parsing file: {check_f}. Error: {e.__class__}, {e}")
        else:
            error(f"Unknown check file path type: {check_f}")

    return all_conf

def trigger_notisfile(file_path):
    """Trigger if the file doesn't exist

    Args:
        file (str): File path to check
    """
    return not os.path.isfile(file_path)

def execute_check(checks_confs):
    """Execute the check based on the configuration provided

    Args:
        checks_confs (dict): Checks configuration provided

    Returns:

    """
    for check_conf in checks_conf


def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION, formatter_class=CustomFormatter)
    parser.add_argument("-c", "--checks-files", required=True,
        help="YAML Configuration Files which contain checks to perform. Can be multiple files"
            "split with ',' OR a directory")
    parser.add_argument("-r", "--regex", default=".*", help="Regex specifying which checks file to parse and exec")
    parser.add_argument("-of", "--outfolder", default="outfolder", help="Output folder")
    parser.add_argument("-t", "--targets", default="", help="List of Targets (comma-separated)")
    parser.add_argument("-s", "--settings", help="Settings KV pair to use for each target")
    
    args = parser.parse_args()

    

    for c in args.checks_file
    

if __name__ == "__main__":
    sys.exit(main())