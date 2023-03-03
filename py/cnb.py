#!/usr/bin/env python

"""
cnb.py [-d] part-of-branch-name [dir-to-create]

If dir-to-create is not supplied, part-of-branch-name is used in its place.

Create a directory into which to clone a new copy of the repo.

Use part-of-branch-name to obtain a list of matching branches. If there's
only one, checkout that branch immediately. If there's more than one (but
less than an arbitrarily large number, select which one you want and check
it out.

If the -d flag is supplied, add extra debug messages.
"""
import configparser
import os
import re
import shutil
import subprocess
import sys
import typing

from configparser import ConfigParser
from pathlib import Path
from subprocess import TimeoutExpired
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


def debug_msg(msg: str) -> None:
	if am_debugging:
		print(msg)

def set_debug(debug: bool=True) -> bool:
	""" Set a new debugging state; return the old one """
	global am_debugging
	old = am_debugging
	am_debugging = debug
	debug_msg("Debugging enabled")
	return old
	

def fail(reason: str, 
		 git_dir: str=None,
		 dir: str=None,
		 exit_val: int=1) -> None:
	"""
	Output a message to stderr, and exit with a given value, or 1 if not given
	"""
	print(f"{sys.argv[0]}: {reason}", file=sys.stderr)

	if git_dir and dir and Path(dir).is_dir():
		if input_char(None, f"Delete directory {dir} (y/n)? ", "ny"):
			try:
				# Get back to safety before deletion
				os.chdir(git_dir)
				shutil.rmtree(dir)
			except Exception as e:
				print(f"Tried to remove {dir} but failed: {str(e)}")
	
	sys.exit(exit_val)
	

def input_char(preamble: str, prompt: str, opt_chr: str) -> int:
	"""
	Prompt the user, and obtain one of the characters from
	opt_chr. Repeat the prompt if the user pressed ENTER
	without entering anything. Repeat the preamble and
	prompt if the user entered something wrong.
	Return the index into opt_chr of the selected character.
	"""
	while True:
		if preamble:
			print(preamble)
			
		while True:
			reply = input(prompt)
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


def run_cmd(command: List, explanation: str=None) -> Tuple[int, str, str]:
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
		
					  
	process = subprocess.run(command, capture_output=True, encoding='UTF-8')

	debug_msg("...done.")

	return (process.returncode, process.stdout, process.stderr)
		

	
def get_config_file(home_dir: str,
					validator: Callable[[ConfigParser], None]=None) -> ConfigParser:
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
			parser = configparser.ConfigParser()
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
	
	
def validate_config_file(parser: ConfigParser) -> None:
	"""
	Attempt to validate the config file. Raise CNBException
	on failure.
	"""
	needed_sects = [ GIT_SECT ]
	
	for sect in needed_sects:		
		if sect not in parser:
			print(f"couldn't find a {sect} section in {cfg_path}")
		
	needed_git_items = [ GIT_REPO_DIR, GIT_REPO_URL ]

	git_sect = parser[GIT_SECT]
	for git_item in needed_git_items:
		if git_item not in git_sect:
			raise CNBException(f"couldn't find the item {git_item} in the config file's {GIT_SECT} section")

	
def get_git_dir(home_dir: str, parser: ConfigParser) -> str:
	"""
	Obtain the user's git directory from the "user.cfg" or 
	".user.cfg" file in their home directory. If no config
	file exists, use the "git" subdirectory of the user's home directory.
	If that doesn't exist, give up and return None.
	"""
	git_dir = None
		
	try:
		git_dir = parser[GIT_SECT][GIT_DIR]

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

	
def clone_repo(parser: ConfigParser) -> bool:
	"""
	Clone the repo into this directory.
	"""
	git_sect = parser[GIT_SECT]
	repo_url = git_sect[GIT_REPO_URL]
	
	(result, _, stderr) = run_cmd(["git", "clone", repo_url],
								  "Cloning the repo...")

	if result != 0:
		raise CNBException(f"couldn't clone {repo_url}: error code {result}\n{stderr}")
		
	repo_dir = git_sect[GIT_REPO_DIR]
	try:
		os.chdir(repo_dir)
	except Exception as e:
		raise CNBException(f"after cloning {repo_url}, couldn't chdir({repo_dir})")

		
def get_branch_name(branch_no: str, parser: ConfigParser) -> str:
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
		git_sect = parser[GIT_SECT]
	except:
		raise CNBException(f"the config file doesn't have a {GIT_SECT} section")
	
	try:
		pass_branches = re.split('\W+', git_sect[GIT_PASS_BRANCHES])
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

	strip_prefix = git_sect.get(GIT_STRIP_PREFIX, 'DO NOT MATCH THIS!')
	branches = [
		branch.replace("*", "").replace(strip_prefix, '').strip()
			for branch
				in stdout.splitlines(keepends=False)
	]
	
	accept_strings_s = git_sect.get(GIT_ACCEPT_RE_LIST, None)
	if accept_strings_s:
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

	
def checkout_branch(branch: str) -> None:
	"""
	Attempt to checkout the branch
	"""
	ok = True
	fail_msg = None
	(result, _, stderr) = run_cmd(["git", "checkout", branch], 
								  f"Checking out {branch}...")
	if result != 0:
		raise CNBException(f"couldn't checkout {branch}: error code {result}\n{stderr}")

	
def main() -> None:
	""" The main function """
	branch_no = None
	dir_name = None
	dir_path_name = None
	home_dir = os.path.expanduser("~")

	try:
		parser = get_config_file(home_dir, validate_config_file)
		git_dir = get_git_dir(home_dir, parser)
		
		num_args = len(sys.argv) - 1
		args_exp = "one or two arguments expected"
		if num_args < 1 or num_args > 2:
			fail(args_exp, git_dir)
		branch_no = sys.argv[1]
		dir_name = sys.argv[2] if num_args == 2 else branch_no

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
		
		branch_name = get_branch_name(branch_no, parser)
		if branch_name == None:
			raise CNBException(f"couldn't get a branch name for {branch_no}")
			
		checkout_branch(branch_name)
	except CNBException as e:
		fail(str(e), git_dir, dir_path_name)
	except Exception as e:
		fail(f"Unexpected exception: {str(e)}", git_dir, dir_path_name)

	print("All complete.")


if __name__ == "__main__":
	if len(sys.argv) > 1 and sys.argv[1] == "-d":
		sys.argv = [ sys.argv[0] ] + sys.argv[2:]
		set_debug()

	main()