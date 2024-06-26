#!/usr/bin/env python3
'''
Forensic tool for git repositories.

Analyses a git repository and produces a JSON file summarising each file change.
'''
import argparse
import datetime
import git
import json
import os
import sys

__authors__   = ["Kitserve <kitserve at users dot noreply dot github dot com>"]
__copyright__ = "2024 Kitson Consulting Limited"
__group__     = "git-log-json"
__license__   = "GPLv3 or later"

def main(argv):
	argumentParser = argparse.ArgumentParser(description='Git commit analyser')
	argumentParser.add_argument('-p', '--path', help='Path to Git directory', required=True)
	argumentParser.add_argument('-b', '--branch', help='Branch to analyse, defaults to the current active branch', required=False)
	argumentParser.add_argument('-o', '--output-file', help='Name of analysis results file', required=True)
	argumentParser.add_argument('-d', '--debug', help='Output extra debugging information', default=False, action='store_true')
	args = vars(argumentParser.parse_args())

	# Validate args and exit if any are incorrect
	path = os.path.realpath(args['path'])

	if not os.path.isdir(path):
		print(f'{args["path"]} is not a directory. Terminating.', file=sys.stderr)
		sys.exit(1)

	try:
		repo = git.Repo(path)
	except git.exc.InvalidGitRepositoryError:
		print(f'{path} is not a valid git repository. Terminating.', file=sys.stderr)
		sys.exit(2)

	if args['debug']:
		print(f'Debug: repo "{path}" is {"not " if not repo.bare else ""}bare.', file=sys.stderr)
		# @see https://github.com/gitpython-developers/GitPython/issues/633
		try:
			print(f'Debug: repo "{path}" is currently on branch "{repo.active_branch}".', file=sys.stderr)
		except:
			print(f'Debug: repo "{path}" is currently in detached head state.', file=sys.stderr)

	# Warn if there are changes that haven't yet made it into Git history
	if repo.is_dirty():
		print(f'Warning: repo "{path}" is dirty. The following files have been modified:', file=sys.stderr)
		for item in repo.index.diff(None):
			print(f' {item.a_path}', file=sys.stderr)

	if len(repo.untracked_files):
		print(f'Warning: repo "{path}" contains the following untracked files:', file=sys.stderr)
		for file in repo.untracked_files:
			print(f' {file}', file=sys.stderr)

	try:
		# Default to current active branch
		if args['branch'] is None:
			branch = repo.active_branch
	except Exception as e:
		print(f'Error: repo "{path}" is in detached head state. Error details:\n{e}\nExiting.', file=sys.stderr)
		sys.exit(4)

	# Check that the requested branch exists in the repo
	else:
		branch = None
		for ref in repo.references:
			if args['branch'] == 'main':
				if 'main' == ref.name:
					branch = 'main'
					break
				elif 'master' == ref.name:
					branch = 'master'
					break
			else:
				if args['branch'] == ref.name:
					branch = args['branch']
					break

		if not branch:
			print(f'Branch "{args["branch"]}" not found in repo "{path}". Terminating.', file=sys.stderr)
			sys.exit(3)

	total_commits = 0
	total_revisions = 0

	first_entry = True

	# @note We should probably be using git.diff.Diffable.NULL_TREE instead of this.
	# @see https://github.com/gitpython-developers/GitPython/issues/364
	# @see https://stackoverflow.com/questions/33916648/get-the-diff-details-of-first-commit-in-gitpython
	EMPTY_TREE_SHA = '4b825dc642cb6eb9a060e54bf8d69288fbee4904'

	with open(args['output_file'], 'w') as output_file:
		output_file.write('[')

		if args['debug']:
			output_file.write('\n')

		# iter_commits() returns an iterator rather than a list, so we need to output each revision record as a separate JSON string
		for commit in repo.iter_commits(rev=branch):
			previous_commit = commit.parents[0] if commit.parents else EMPTY_TREE_SHA

			diffs = {
				diff.a_path: diff for diff in commit.diff(previous_commit, R=True)
			}

			for file, stats in commit.stats.files.items():
				diff = diffs.get(file)

				if not diff:
					for diff in diffs.values():
						if diff.b_path == path and diff.renamed:
							break

				# @see https://git-scm.com/docs/git-status
				if diff.change_type == ' ':
					status = 'Not modified'
				elif diff.change_type == 'M':
					status = 'Modified'
				elif diff.change_type == 'T':
					status = 'File type changed'
				elif diff.change_type == 'A':
					status = 'Added'
				elif diff.change_type == 'D':
					status = 'Deleted'
				elif diff.change_type == 'R':
					status = 'Renamed'
				elif diff.change_type == 'C':
					status = 'Copied'
				elif diff.change_type == 'U':
					status = 'Updated but unmerged'
				else:
					status = 'Unknown'

				if not first_entry:
					output_file.write(',')

				if args['debug']:
					if not first_entry:
						output_file.write('\n')
					output_file.write(json.dumps({'revision': commit.hexsha, 'author': commit.author.name, 'email': commit.author.email, 'date': datetime.datetime.fromtimestamp(commit.committed_date).isoformat(), 'message': commit.message.strip(), 'modified': file, 'extension': f'.{os.path.basename(file).split('.')[-1]}', 'status': status, 'lines_added': stats['insertions'], 'lines_removed': stats['deletions']}, indent=1))
				else:
					output_file.write(json.dumps({'revision': commit.hexsha, 'author': commit.author.name, 'email': commit.author.email, 'date': datetime.datetime.fromtimestamp(commit.committed_date).isoformat(), 'message': commit.message.strip(), 'modified': file, 'extension': f'.{os.path.basename(file).split('.')[-1]}', 'status': status, 'lines_added': stats['insertions'], 'lines_removed': stats['deletions']}))

				total_revisions += 1
				first_entry = False

			total_commits += 1

		if args['debug']:
			output_file.write('\n')

		output_file.write(']')

		if args['debug']:
			output_file.write('\n')

	if args['debug']:
		print(f'Debug: wrote {total_revisions} file modification record(s) from {total_commits} commit(s) in repo "{path}" on branch "{branch}" to JSON file "{args["output_file"]}".')

if __name__ == '__main__':
	main(sys.argv)
