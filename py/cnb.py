#!/usr/bin/env python
# coding: future-fstrings
"""
cnb.py [-d] [-l] part-of-branch-name [dir-to-create]

If dir-to-create is not supplied, part-of-branch-name is used in its place.

Create a directory into which to clone a new copy of the repo.

Use part-of-branch-name to obtain a list of matching branches. If there's
only one, checkout that branch immediately. If there's more than one (but
less than an arbitrarily large number, select which one you want and check
it out.

If the -d flag is supplied, add extra debug messages.

If the -l flag is supplied, matching will be looser. Anything that matches
the part-of-branch-name will be accepted. This may lead to too many matches!
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import traceback
import typing

if sys.version_info[0] == 2:	
	from ConfigParser import ConfigParser
	class TimeoutExpired(Exception): pass
else:
	from configparser import ConfigParser
	from subprocess import TimeoutExpired
from pathlib import Path
from typing import Callable, List, Tuple

GIT_SECT = 'git'
GIT_DIR = 'dir'
GIT_REPO_DIR = 'repo_dir'
GIT_REPO_URL = 'repo_url'
GIT_PASS_BRANCHES = 'pass_branches'
GIT_STRIP_PREFIX = 'strip_prefix'
GIT_ACCEPT_RE_LIST = 'accept_re_list'

am_debugging = False

class CNBException(Exception):
	pass


def explain_exception():
	# type: () -> None
	traceback.print_exc()

def debug_msg(msg):
	# type: (str) -> None
	if am_debugging:
		print(msg)

def set_debug(debug=True):
	# type: (bool) -> bool
	""" Set a new debugging state; return the old one """
	global am_debugging
	old = am_debugging
	am_debugging = debug
	debug_msg("Debugging enabled")
	return old
	

def input_char(preamble, prompt, opt_chr):
	# type: (str, str, str) -> int
	"""
	Prompt the user, and obtain one of the characters from
	opt_chr. Repeat the prompt if the user pressed ENTER
	without entering anything. Repeat the preamble and
	prompt if the user entered something wrong.
	Return the index into opt_chr of the selected character.
	"""
	input_fn = lambda prompt: input(prompt) if sys.version_info[0] > 2 \
											else raw_input(prompt)
	while True:
		if preamble:
			print(preamble)
			
		while True:
			reply = input_fn(prompt)
			reply_len = len(reply)
			if reply_len == 1:
				index = opt_chr.find(reply[0])
				if index < 0:
					print("*** Not one of the available options! ***")
					break
				else:
					return index
			elif reply_len > 1:
				print("*** Please only type one character! ***")


def fail(reason, git_dir='', dir='', exit_val=1):
	# type: (str, str, str, int) -> None
	"""
	Output a message to stderr, and exit with a given value, or 1 if not given
	"""
	sys.stderr.write(f"{sys.argv[0]}: {reason}\n")

	if git_dir and dir and Path(dir).is_dir():
		if input_char('', f"Delete directory {dir} (y/n)? ", "ny"):
			try:
				# Get back to safety before deletion
				os.chdir(git_dir)
				shutil.rmtree(dir)
			except Exception as e:
				print(f"Tried to remove {dir} but failed: {str(e)}")
	
	sys.exit(exit_val)
	

def run_cmd(command, explanation=''):
	# type: (List, str) -> Tuple[int, str, str]
	"""
	Run a task.
	
	Returns a tuple of process return value, stdout (or None if
	realtime_stdout is True) and stderr.
	"""
	
	discuss = (explanation is None or explanation != '')
	
	if discuss:
		if am_debugging:
			debug_msg(explanation if explanation 
							  else f"About to run {' '.join(command)}")
		elif explanation:
			print(explanation)
		
					  
	process = subprocess.Popen(command,
			    			   stdout=subprocess.PIPE,
							   stderr=subprocess.PIPE)
	stdout, stderr = process.communicate()
	returncode = process.returncode

	debug_msg("...done.")

	return (returncode, stdout.decode('UTF-8'), stderr.decode('UTF-8'))


def validate_config_file_no_op(parser):
	# type: (ConfigParser) -> None
	"""	Don't bother validating, just return """
	pass

	
def validate_config_file(parser):
	# type: (ConfigParser) -> None
	"""
	Attempt to validate the config file for the needs of this module.
	Raise CNBException on failure.
	"""
	needed_sects = [ GIT_SECT ]
	sections = parser.sections()
	for sect in needed_sects:		
		if sect not in sections:
			raise CNBException(f"couldn't find a {sect} section in the config file")
		
	needed_git_items = [ GIT_REPO_DIR, GIT_REPO_URL ]

	for git_item in needed_git_items:
		if not parser.has_option(GIT_SECT, git_item):
			raise CNBException(f"couldn't find the item {git_item} in the config file's {GIT_SECT} section")

	
def get_config_file(home_dir, validator=validate_config_file_no_op):
	# type: (str, Callable[[ConfigParser], None]) -> ConfigParser
	"""
	Attempt to load our config file. If it doesn't exist, or is corrupt, give
	up. This is the "user.cfg" or ".user.cfg" file in their home directory.
	"""
	cfg_name = "user.cfg"
	options = [ os.path.join(home_dir, cfg_name), 
				os.path.join(home_dir, "."+cfg_name) ]
	cfg_path = None
	for option in options:
		if os.path.isfile(option):
			cfg_path = option
			break

	parser = None
	if cfg_path:
		try:
			parser = ConfigParser()
			r = parser.read(cfg_path)
			if not r:
				raise Exception(f"config file {cfg_path} could not be parsed")
		except Exception as e:
			parser = None
			debug_msg(f"Could not read {cfg_path}: {str(e)}")
	else:
		debug_msg(f"No configuration file")
		
	if not parser:
		raise CNBException("couldn't find, or couldn't parse, the config file")
		
	if validator:
		validator(parser)
		
	return parser
	
	
def get_git_dir(home_dir, parser):
	# type: (str, ConfigParser) -> str
	"""
	Obtain the user's git directory from the "user.cfg" or 
	".user.cfg" file in their home directory. If no config
	file exists, use the "git" subdirectory of the user's home directory.
	If that doesn't exist, give up and return None.
	"""
	git_dir = None
		
	try:
		git_dir = parser.get(GIT_SECT, GIT_DIR)

		if '~' in git_dir:
			git_dir = git_dir.replace('~', home_dir)
		
		# We may have a mix of path separators here, so standardise
		p = Path(git_dir)
		# But ignore it if it doesn't exist
		if p.is_dir():
			git_dir = str(p)
		else:
			debug_msg(f"We got git path {git_dir} from the config file, but it")
			debug_msg("doesn't exist, so we'll try for the default place.\n")
			git_dir = None
	except Exception as e:
		explain_exception()
		debug_msg(f"Hmmm - can't get a git dir from the config file: {str(e)}")
		pass
		
	if not git_dir:
		p = Path(home_dir, 'git')
		if p.is_dir():
			git_dir = str(p)

	# This really shouldn't be a possibility now, but belt and braces...
	if git_dir and not Path(git_dir).is_dir():
		git_dir = None

	if git_dir == None:
		raise CNBException("can't find any git directory - giving up")

	return git_dir

	
def clone_repo(parser):
	# type: (ConfigParser) -> bool
	"""
	Clone the repo into this directory.
	"""
	repo_url = parser.get(GIT_SECT, GIT_REPO_URL)
	
	(result, _, stderr) = run_cmd(["git", "clone", repo_url],
								  "Cloning the repo...")

	if result != 0:
		raise CNBException(f"couldn't clone {repo_url}: error code {result}\n{stderr}")
		return False # NOTREACHED
		
	repo_dir = parser.get(GIT_SECT, GIT_REPO_DIR)
	try:
		os.chdir(repo_dir)
	except Exception as e:
		explain_exception()
		raise CNBException(f"after cloning {repo_url}, couldn't chdir({repo_dir})")
		return False # NOTREACHED
	
	return True

		
def get_branch_name(branch_no, parser, loose):
	# type: (str, ConfigParser, Bool) -> str
	"""
	Given a branch number (or similar substring), obtain and return the actual
	branch name the user wants to use. If necessary, the user is prompted for
	one of a number of alternatives.
	"""
	
	#
	# Check if the branch name is one of a number we just let through
	#
	passes = [
		"main",
		"master"
	]
	
	try:
		if parser.has_option(GIT_SECT, GIT_PASS_BRANCHES):
			orig_pass_branches = parser.get(GIT_SECT, GIT_PASS_BRANCHES)
			pass_branches = re.split(r'\W+', orig_pass_branches)
			passes += pass_branches
	except:
		pass

	if branch_no in passes:
		return branch_no

	
	#
	# Get the list of branches
	#
	(result, stdout, stderr) = run_cmd(["git", "branch", "-a"],
								       "Getting branches...")

	if result != 0:
		raise CNBException(f"couldn't clone the repo: error code {result}\n{stderr}")

	strip_prefix = 'DO NOT MATCH THIS!'
	if parser.has_option(GIT_SECT, GIT_STRIP_PREFIX):
		strip_prefix = parser.get(GIT_SECT, GIT_STRIP_PREFIX)

	branches = [
		branch.replace("*", "").replace(strip_prefix, '').strip()
			for branch
				in stdout.splitlines()
	]

	# Only attempt to restrict matches if not being loose
	if parser.has_option(GIT_SECT, GIT_ACCEPT_RE_LIST) and not loose:
		accept_strings_s = parser.get(GIT_SECT, GIT_ACCEPT_RE_LIST)
		accept_strings = accept_strings_s.split(',')
		new_branches = [
			branch
				for branch in branches
					for a_s in accept_strings
						if re.search(a_s, branch)
		]
		branches = new_branches
		
	# Now find out how many match our branch_no
	match_branches = [
		branch
			for branch in branches
				if branch_no in branch
	]
	
	opt_str = "0123456789abcdefghijklmnopqrstuvwxyz"

	num_matches = len(match_branches)
	
	if num_matches == 0:
		raise CNBException(f"couldn't find any branches matching {branch_no}")
	elif num_matches == 1:
		return match_branches[0]
	elif num_matches > len(opt_str):
		raise CNBException(f"{num_matches} branches matching {branch_no} but our limit is {len(opt_str)}")
		
	options = ""
	for ix in range(0, num_matches):
		options += f"{opt_str[ix]} - {match_branches[ix]}\n"

	index = input_char(options,
					   "Select branch: ",
					   opt_str[:num_matches])
	
	return match_branches[index]

	
def checkout_branch(branch):
	# type: (str) -> None
	"""
	Attempt to checkout the branch
	"""
	ok = True
	fail_msg = None
	(result, _, stderr) = run_cmd(["git", "checkout", branch], 
								  f"Checking out {branch}...")
	if result != 0:
		raise CNBException(f"couldn't checkout {branch}: error code {result}\n{stderr}")

	
def main(args):
	# type: (argparse.Namespace) -> None
	""" The main function """
	branch_no = args.branch_no
	dir_name = args.dir_name if args.dir_name else branch_no
	dir_path_name = ''
	home_dir = os.path.expanduser("~")
	git_dir = ''

	try:
		parser = get_config_file(home_dir, validate_config_file)
		git_dir = get_git_dir(home_dir, parser)
		
		dir_path = Path(git_dir, dir_name)
		dir_path_name = str(dir_path)
		if dir_path.exists():
			raise CNBException(f"something called {dir_path_name} exists. Remove it first!")

		try:
			dir_path.mkdir()
		except Exception as e:
			raise CNBException(f"couldn't create {dir_path_name}: {str(e)}")
			
		try:
			os.chdir(dir_path_name)
		except Exception as e:
			raise CNBException(f"couldn't cd to {dir_path_name}: {str(e)}")		
		
		clone_repo(parser)
		
		branch_name = get_branch_name(branch_no, parser, args.loose)
		if branch_name == None:
			raise CNBException(f"couldn't get a branch name for {branch_no}")
			
		checkout_branch(branch_name)
	except CNBException as e:
		explain_exception()
		fail(str(e), git_dir, dir_path_name)
	except Exception as e:
		explain_exception()
		fail(f"Unexpected exception: {str(e)}", git_dir, dir_path_name)

	print("All complete.")


if __name__ == "__main__":

	parser = argparse.ArgumentParser(
		prog="cnb",
		description="Create a clone of a new branch")
		
	parser.add_argument('-d', '--debug', 
						action='store_true',
						help='enable debugging messages')
	parser.add_argument('-l', '--loose',
						action='store_true',
						help='enable looser matching')
	parser.add_argument('branch_no',
						help='part of branch name to match, typically the number from a DT-xxx JIRA task')
	parser.add_argument('dir_name',
						nargs='?',
						default=None,
						help='directory name to create (default branch_part)')
	args = parser.parse_args()
	
	if args.debug:
		set_debug(True)

	main(args)