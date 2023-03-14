#!/usr/bin/env python
# coding: future-fstrings
"""
getconf.py -d cmd [cmd_args...]

Get configuration information. Commands:

gd							Get the git directory
cnf sect item 				Get item "item" from conf file section "sect"
"""
import os
import sys
import typing

if sys.version_info[0] == 2:	
	from ConfigParser import ConfigParser
else:
	from configparser import ConfigParser

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

from cnb import CNBException, get_config_file, get_git_dir, set_debug, explain_exception


def fail(reason):
	# type: (str) -> None
	if reason:
		sys.stderr.write(f"{sys.argv[0]}: {reason}\n")
	sys.exit(1)

	
def validate_config_file(parser):
	# type: (ConfigParser) -> None
	"""	Don't bother validating, just return """
	pass


def validate_section(sect_name, parser):
	# type: (str, ConfigParser) -> None
	# Yes, I'd like to use "get()", but for some reason I get
	# 'NoneType' object has no attribute 'lower'.
	if sect_name not in parser.sections():
		raise CNBException(f"there is no section {sect_name} in the config file")

	
def validate_item(sect_name, item_name, parser):
	# type: (str, str, ConfigParser) -> str
	validate_section(sect_name, parser)
	if not parser.has_option(sect_name, item_name):
		raise CNBException(f"there is no item {item_name} in section {sect_name} in the config file")
	return parser.get(sect_name, item_name)

	
def arg_gd(home_dir, parser):
	# type: (str, ConfigParser) -> None
	print(get_git_dir(home_dir, parser))
	

def arg_cnf(home_dir, parser):
	# type: (str, ConfigParser) -> None
	sect_name = sys.argv[2]
	item_name = sys.argv[3]
	item = validate_item(sect_name, item_name, parser)
	print(item.strip())
	

def arg_sects(home_dir, parser):
	# type: (str, ConfigParser) -> None
	for sect_name in parser.sections():
		print(sect_name)
		
		
def arg_items(home_dir, parser):
	# type: (str, ConfigParser) -> None
	sect_name = sys.argv[2]
	validate_section(sect_name, parser)
	for item_name in parser.options(sect_name):
		print(item_name)

	
def main():
	# type: () -> None
	home_dir = os.path.expanduser("~")

	# Command lookup. The key is the name of the command; the value
	# is a list of the number of subsequent arguments and the handler
	# function.
	cmds = {
		"gd":		[0, arg_gd],
		"cnf":		[2, arg_cnf],
		"sects":	[0, arg_sects],
		"items":	[1, arg_items],
	}

	try:
		parser = get_config_file(home_dir, validate_config_file)

		num_args = len(sys.argv) - 1

		if num_args == 0:
			raise CNBException("at least one argument expected")

		cmd = sys.argv[1]
		value = cmds.get(cmd)
		
		if value == None:
			raise CNBException("unknown argument")
		elif value[0] != (num_args - 1):
			raise CNBException(f"command {cmd} takes {value[0]} arguments, not {num_args-1}")
		else:
			value[1](home_dir, parser)
			
	except Exception as e:
		fail(str(e))

if __name__ == "__main__":
	if len(sys.argv) > 1 and sys.argv[1] == "-d":
		sys.argv = [ sys.argv[0] ] + sys.argv[2:]
		set_debug()

	main()