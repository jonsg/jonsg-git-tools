#!/usr/bin/env python

"""
getconf.py -d cmd [cmd_args...]

Get configuration information. Commands:

gd							Get the git directory
cnf sect item 				Get item "item" from conf file section "sect"
"""
import os
import sys
import typing

from configparser import ConfigParser

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.dirname(SCRIPT_DIR))

from cnb import CNBException, get_config_file, get_git_dir, set_debug


def fail(reason: str) -> None:
	if reason:
		sys.stderr.write(f"{sys.argv[0]}: {reason}\n")
	sys.exit(1)

	
def validate_config_file(parser: ConfigParser) -> None:
	pass


def validate_section(sect_name: str, parser: ConfigParser) -> str:
	sect_name = sys.argv[2]
	# Yes, I'd like to use "get()", but for some reason I get
	# 'NoneType' object has no attribute 'lower'.
	if sect_name not in parser:
		raise CNBException(f"there is no section {sect_name} in the config file")
	return parser[sect_name]

	
def validate_item(item_name: str, sect_name: str, parser: ConfigParser) -> str:
	sect = validate_section(sect_name, parser)
	item_name = sys.argv[3]
	if item_name not in sect:
		raise CNBException(f"there is no item {item_name} in section {sect_name} in the config file")
	return item

	
def arg_gd(home_dir: str, parser: ConfigParser) -> None:
	print(get_git_dir(home_dir, parser))
	

def arg_cnf(home_dir: str, parser: ConfigParser) -> None:
	item = validate_item(item_name, sect_name, parser)
	print(item.strip())
	

def arg_sects(home_dir: str, parser: ConfigParser) -> None:
	[ print(sect_name) for sect_name in parser.sections() ]
		
		
def arg_items(home_dir: str, parser: ConfigParser) -> None:
	sect = validate_section(sys.argv[2], parser)
	[ print(item_name) for item_name in sect ]
	
def main() -> None:
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