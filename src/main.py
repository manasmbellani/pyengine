#!/usr/bin/env python3
import argparse
import os
import re
import shutil
import subprocess
import sys

import requests
import yaml
from termcolor import colored

DESCRIPTION = "Script to parse checks files, and execute commands"

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/106.0.0.0 Safari/537.36"

INPUTS_REGEX = "\{(?P<input>[a-zA-Z0-9_\-]+)\}"

SEPERATOR = "-" * 60 + "\n\n"

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
    e = colored("[-] ", 'red') + msg
    print(e)
    return e

def debug(msg):
    """
    Print debug message

    Args:
        msg (str): Debug message

    Returns:
        str: Message string
    """
    m = colored("[*] ", 'white') + msg
    print(m)
    return m

def warning(msg):
    """
    Print warning message

    Args:
        msg (str): Warning message

    Returns:
        str: Message string
    """
    m = colored("[!] ", 'yellow') + msg
    print(m)
    return m

def info(msg):
    """
    Print info

    Args:
        msg (str): Info message

    Returns:
        str: Message string
    """
    m = colored("[+] ", 'blue') + msg
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
        warning(msg)
        msgs_txt.append(msg)

    return "\n".join(msgs_txt)

def task_notes(notes, conf):
    """Print notes

    Args:
        notes (str): Notes
        conf (dict): Configuration with settings to substitute in cmd

    Returns:
        str: Notes to print
    """
    all_notes = []

    if notes:
        if isinstance(notes, str):
            notes = [notes]
        
        for note in notes:
            note = sub_conf(note, conf)
            warning(note)
            all_notes.append(note)
        
        # Additional Blank space
        warning('')
        warning('')

    return all_notes

def task_cmd(cmds, conf, cmd_dir=''):
    """Execute command(s)

    Args:
        cmds (str/list): Shell command(s) to execute
        conf (dict): Configuration with settings to substitute in cmd
        cmd_dir (str): Command directory

    Returns:
        (bool, str): Boolean on whether the command was executed AND output
    """
    was_cmd_successful = False
    out_text = ""

    if cmds:
        # Setup the current working directory
        cwd = os.getcwd()
        if cmd_dir:
            if os.path.isdir(cmd_dir):
                os.chdir(cmd_dir)
            else:
                error(f"Cmd directory: {cmd_dir} does not exist")

        if isinstance(cmds, str):
            cmds = [cmds]
        
        # Join all commands together to execute in the shell
        cmd_to_exec = "; ".join(cmds)

        for c in cmds:
            try:
                debug(f"Executing command: {cmd_to_exec}...")
                p = subprocess.Popen(sub_conf(cmd_to_exec, conf), shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                out, __ = p.communicate()
                out_text = out.decode().strip()
                was_cmd_successful = True
            except Exception as e:
                error(f"Error executing command: {c}. Error: {e.__class__}, {e}")

        # Switch back to the current dir
        if cmd_dir:
            os.chdir(cwd)

    else:
        error("No cmds provided")
        
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

def parse_input_files(input_files):
    """Parsing the input files to return the settings

    Args:
        input_file (str): Path to input file OR folder which contains input files

    Returns:
        dict: A dictionary of settings
    """
    settings = {}
    input_files = input_files.split(',')
    for input_file in input_files:
        if os.path.isfile(input_file):
            debug(f"Parsing input from file: {input_file}...")
            with open(input_file, "r") as f:
                settings[input_file] = yaml.safe_load(f)
        elif os.path.isdir(input_file):
            input_folder = input_file
            for dp, _, files in os.walk(input_folder):
                for f in files:
                    p = os.path.join(dp, f)
                    debug(f"Parsing input from file: {p}...")
                    with open(p, "r+") as f:
                        settings[p] = yaml.safe_load(f)
        else:
            error(f"Input file/folder: {input_file} does not exist")
    
    return settings

def parse_checks_files(checks_files, regex):
    """Parse the checks files and also identifies the inputs

    Args:
        checks_file (str): Checks files
        regex (str): Regex specifying which checks files to parse/execute

    Returns:
        (dict, list) : A list of checks file configuration for each file parsed and list of inputs
    """
    all_conf = {}
    all_inputs = set()
    checks_fs = checks_files.split(",")

    for check_f in checks_fs:
        if os.path.isfile(check_f.strip()):
            # Check if file should be executed
            m = re.search(regex, check_f, re.I)

            if m:
                debug(f"Parsing conf file: {check_f} for inputs and YAML config...")
                with open(check_f.strip(), "r") as fo:

                    # Identifying the inputs
                    inputs = re.findall(INPUTS_REGEX, fo.read(), re.M|re.I)
                    for input in inputs:
                        all_inputs.add(input)

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

                    m = re.search(regex, p, re.I)
                    if m:
                        debug(f"Parsing conf file: {p} for inputs and YAML config...")
                        with open(p, "r") as fo:
                            inputs = re.findall(INPUTS_REGEX, fo.read(), re.M|re.I)
                            for input in inputs:
                                all_inputs.add(input)
                        
                        with open(p, "r") as fo:
                            try:
                                yaml_conf = yaml.safe_load(fo)
                                all_conf[p] = yaml_conf
                            except Exception as e:
                                error(f"Error parsing file: {check_f}. Error: {e.__class__}, {e}")
        else:
            error(f"Unknown check file path type: {check_f}")

    return all_conf, list(all_inputs)

def create_outfolder(outfolder):
    """Create the output folder

    Args:
        outfolder (str): Output folder
    """
    if os.path.isdir(outfolder):
        debug(f"Removing existing outfolder: {outfolder}...")
        shutil.rmtree(outfolder)

    debug(f"Creating outfolder: {outfolder}...")
    os.mkdir(outfolder)

def execute_checks(checks_confs, settings, out_folder):
    """Execute the check based on the configuration files provided

    Args:
        checks_confs (dict): Checks configuration provided
        settings (dict): Settings
        out_folder (str): Output folder to write the output
    """
    for check_conf_file, conf in checks_confs.items():
        debug(f"Executing conf from file: {check_conf_file}...")
        summary = conf.get('summary')
        if summary:
            debug(f"Summary: {summary}")
        description = conf.get('description')
        if description:
            debug(f"Description: {description}...")
        task_config = conf.get('task')
        if task_config:
            task_type = task_config.get('task_type', 
                        task_config.get('type'))
            if task_type == 'cmd':
                cmds = task_config.get('cmd', 
                      task_config.get('cmds', []))
                cmd_dir = task_config.get('cmd_dir', 
                          task_config.get('dir', ''))
                was_cmd_successful, output = task_cmd(cmds, settings, 
                    cmd_dir=cmd_dir)
                
                info(f"Output of cmd:\n{output}")
                info('')
                info('')
            elif task_type == 'notes':
                pass
            else:
                error(f"Error executing task of type: {task_type}")

            #elif (task_type == 'web_request' or task_type == 'web_request'):    
            #elif (task_type == 'notes'):
            # Print any notes
            notes = task_config.get('notes',
                    task_config.get('note'))
            task_notes(notes, settings)

        # Separate each task
        print(SEPERATOR)
            

def check_if_all_inputs_supplied(inputs, settings):
    """Check if all inputs supplied in settings

    Args:
        inputs (list): Inputs found in the checks file
        settings (dict): Settings parsed from inputs file
    """
    all_inputs_supplied = True
    for input in inputs:
        if input not in settings:
            error(f"input: {input} not supplied in settings")
            all_inputs_supplied = False

    return all_inputs_supplied

def main():
    parser = argparse.ArgumentParser(description=DESCRIPTION, formatter_class=CustomFormatter)
    parser.add_argument("-c", "--checks-files", required=True,
        help="YAML Configuration Files which contain checks to perform. Can be multiple files"
            "split with ',' OR a directory")
    parser.add_argument("-i", "--input-file", required=True, 
        help="Input file in YAML format to execute the checks on which contains a dictionary")
    parser.add_argument("-r", "--regex", default=".*", help="Regex specifying which checks file to parse and exec")
    parser.add_argument("-of", "--outfolder", default="outfolder", help="Output folder")
    parser.add_argument("-t", "--targets", default="", help="List of Targets (comma-separated)")
    
    args = parser.parse_args()

    create_outfolder(args.outfolder)

    checks_confs, inputs_to_get = parse_checks_files(args.checks_files, args.regex)

    settings = parse_input_files(args.input_file)

    for f, settings_f in settings.items():
        debug(f"Executing checks for file: {f}...")
        if check_if_all_inputs_supplied(inputs_to_get, settings_f):
            # Separate each task
            print(SEPERATOR)

            # Start executing checks
            execute_checks(checks_confs, settings_f, args.outfolder)

    return 0

if __name__ == "__main__":
    sys.exit(main())