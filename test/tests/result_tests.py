import copy
import datetime
import json
import logging
import pprint
from collections import OrderedDict

import pavilion.result
import pavilion.result.common
import yaml_config as yc
from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion import result
from pavilion import utils
from pavilion.plugins.commands import run
from pavilion.result import parsers, ResultError, base
from pavilion.test_run import TestRun
from pavilion.unittest import PavTestCase

LOGGER = logging.getLogger(__name__)


class ResultParserTests(PavTestCase):

    def setUp(self):
        # This has to run before any command plugins are loaded.
        arguments.get_parser()
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    def test_parse_results(self):
        """Check all the different ways in which we handle parsed results."""

        test_cfg = {
            'scheduler': 'raw',
            'run': {
                # This will result in 4 output files.
                # run.log, other.log, other2.log, other3.log
                'cmds': [
                    'echo "Hello World."',
                    'echo "Goodbye Cruel World."',
                    'echo "Multipass 1, 2, 3"',
                    'echo "A: 1"',
                    'echo "B: 2"',
                    'echo "B: 3"',
                    'echo "C: 4"',
                    'echo "D: 5"',
                    'echo "B: 6"',
                    'echo "D: 7"',
                    'echo "E: 8"',
                    'echo "In a World where..." >> other.log',
                    'echo "something happens..." >> other2.log',
                    'echo "and someone saves the World." >> other3.log',
                    'echo "I\'m here to cause Worldwide issues." >> other.txt'
                ]
            },
            'result_parse': {
                'regex': {
                    'basic': {'regex': r'.* World'},
                    'bc': {
                        'regex': r'.: (\d)',
                        'preceded_by': [r'^B:', r'^C:'],
                        'match_select': 'all',
                    },
                    'bcd': {
                        'regex': r'.: (\d)',
                        'preceded_by': [r'^B:', r'^C:'],
                        'for_lines_matching': r'^D:',
                        'match_select': 'all',
                    },
                    'bees': {
                        'regex': r'.: (\d)',
                        'for_lines_matching': r'^B:',
                        'match_select': 'all',
                    },
                    'last_b': {
                        'regex':              r'.: (\d)',
                        'for_lines_matching': r'^B:',
                        'match_select':       'last',
                    },
                    'middle_b': {
                        'regex':              r'.: (\d)',
                        'for_lines_matching': r'^B:',
                        'match_select':       '1',
                    },
                    'other_middle_b': {
                        'regex':              r'.: (\d)',
                        'for_lines_matching': r'^B:',
                        'match_select':       '-2',
                    },
                    'no_lines_match': {
                        'regex':              r'.*',
                        'for_lines_matching': r'nothing',
                        'match_select':       parsers.MATCH_ALL,
                    },
                    'no_lines_match_last': {
                        'regex':              r'.*',
                        'for_lines_matching': r'nothing',
                        'match_select':       parsers.MATCH_FIRST,
                    },
                    'mp1, _  ,   mp3': {
                        'regex': r'Multipass (\d), (\d), (\d)'
                    },
                    'mp4,mp5': {
                        'regex': r'Multipass (\d), (\d), (\d)'
                    },
                    'true': {
                        # Look all the log files, and save 'True' on match.
                        'files': ['../run.log'],
                        'regex': r'.* World',
                        'action': parsers.ACTION_TRUE,
                    },
                    'false': {
                        # As before, but false. Also, with lists of data.
                        # By multiple globs.
                        'files': ['../run.log', 'other.*'],
                        'regex': r'.* World',
                        'action': parsers.ACTION_FALSE,
                    },
                    'count': {
                        # As before, but keep match counts.
                        'files': ['../run.log', '*.log'],
                        'regex': r'.* World',
                        'match_select': parsers.MATCH_ALL,
                        'action': parsers.ACTION_COUNT,
                        'per_file': parsers.PER_NAME,
                    },
                    'name': {
                        # Store matches by name stub
                        # Note there is a name conflict here between other.txt
                        # and other.log.
                        'files': ['other.*'],
                        'regex': r'.* World',
                        'per_file': parsers.PER_NAME,
                    },
                    'name_list': {
                        # Store matches by name stub
                        # Note there is a name conflict here between other.txt
                        # and other.log.
                        'files': ['*.log'],
                        'regex': r'World',
                        'per_file': parsers.PER_NAME_LIST,
                    },
                    'lists': {
                        'files': ['other*'],
                        'regex': r'.* World',
                        'match_select': parsers.MATCH_ALL,
                        'per_file': parsers.PER_LIST,
                    },
                    'all': {
                        'files': ['other*'],
                        'regex': r'.* World',
                        'action': parsers.ACTION_TRUE,
                        'per_file': parsers.PER_ALL
                    },
                    'result': {
                        'files': ['other*'],
                        'regex': r'.* World',
                        'action': parsers.ACTION_TRUE,
                        'per_file': parsers.PER_ANY
                    },
                }
            }
        }

        test = self._quick_test(test_cfg, 'result_parser_test')
        test.run()

        results = test.gather_results(0)

        expected = {
            'basic': 'Hello World',
            'bc': [5],
            'bcd': [5],
            'bees': [2, 3, 6],
            'last_b': 6,
            'middle_b': 3,
            'other_middle_b': 3,
            'no_lines_match': None,
            'no_lines_match_last': None,
            'true': True,
            'false': False,
            'per_file': {
                'other': {
                    'count': 1,
                    'name': 'In a World'},
                'other2': {
                    'count': 0},
                'other3': {
                    'count': 1},
                'run': {
                    'count': 2},
            },
            'mp1': 1,
            'mp3': 3,
            'mp4': 1,
            'mp5': 2,
            'name_list': ['other', 'other3'],
            'lists': [
                "I'm here to cause World",
                "In a World",
                "and someone saves the World"],
            'all': False,
            'result': 'PASS',  # Any test
        }

        for key in expected:
            self.assertEqual(results[key], expected[key])
        self.assertIn(
            "When storing value for key 'name' per 'name', multiple files "
            "normalized to the name 'other': other.txt, other.log",
            results[result.RESULT_ERRORS])

        def find_hidden(resultd: dict) -> set:
            """Find any result bits that start with underscore."""

            found = set()

            for rkey, value in resultd.items():
                if rkey.startswith('_'):
                    found.add(rkey)
                if isinstance(value, dict):
                    found.update(find_hidden(value))

            return found

        self.assertEqual(find_hidden(results), set(),
                         msg="All hidden ('_' prefixed) result keys were "
                             "supposed to be deleted.")

    def test_check_config(self):

        # A list of regex
        parser_tests = [
            # Should work fine.
            ({'ok': {'regex': r'foo'}}, None),
            # Reserved key
            ({'created': {'regex': r'foo'}}, ResultError),
            # Missing regex
            ({'nope': {}}, yc.RequiredError),
            # Error in result parser specific args
            ({'test': {'regex': '[[['}}, ResultError),
            # You can't store the 'result' key 'per_file'.
            ({'result': {'per_file': 'name', 'regex': 'foo'}},
             ResultError),
        ]

        for parsers_conf, err_type in parser_tests:

            test_cfg = self._quick_test_cfg()
            test_cfg['result_parse'] = {
                    'regex': parsers_conf,
                }

            if err_type is not None:
                with self.assertRaises(err_type,
                                       msg="Error '{}' not raised for '{}'"
                                           .format(err_type, parsers_conf)):

                    # We want a finalized, validated config. This may raise
                    # errors too.
                    test = self._quick_test(test_cfg)

                    pavilion.result.check_config(test.config['result_parse'],
                                                 {})
            else:
                test = self._quick_test(test_cfg)
                pavilion.result.check_config(test.config['result_parse'], {})

        evaluate_confs = [
            # Reserved key
            {'started': 'bar'},
            {'foo': 'bar.3 +'}
        ]

        for eval_conf in evaluate_confs:
            with self.assertRaises(ResultError):
                pavilion.result.check_config({}, eval_conf)

    def test_base_results(self):
        """Make all base result functions work."""

        test = self._quick_test(
            cfg={
                # The only required param.
                'name': 'blank_test',
                'scheduler': 'raw',
            })

        now = datetime.datetime.now()

        # Any test that tries to run will have these, and only tests that
        # try to run get results.
        test.started = now
        test.finished = now + datetime.timedelta(seconds=3)
        test.job_id = 'test'

        base_results = base.base_results(test)
        # This one has to be set manually.
        base_results['return_value'] = 0

        for key in base.BASE_RESULTS.keys():
            self.assertIn(key, base_results)
            # Base result keys should have a non-None value, even from an
            # empty config file.
            self.assertIsNotNone(
                base_results[key],
                msg="Base result key '{}' was None.".format(key))

    def test_table_result_parser(self):
        """
        Makes sure Table Result Parser Works
        :return:
        """

        # start & nth start with line+space delimiter
        table_test_start_nth = {
            'scheduler': 'raw',
            'build': {
                'source_path': 'tables.txt'
            },
            'run': {
                'cmds': [
                    'cat tables.txt'
                ]
            },
            'result_parse': {
                'table': {
                    'stuff_table': {
                        'delimiter': r'\|',
                        'col_num': '3',
                        'col_names': ['Col1', 'Col2', 'Col3'],
                        'start_re': r'^stuff',
                        'nth_start_re': '1'
                    }
                }
            }
        }

        start_table_test = self._quick_test(table_test_start_nth,
                                            'result_parser_test')
        start_table_test.run()
        start_results = {'pav_result_errors': []}
        parsers.parse_results(start_table_test, start_results)

        self.assertEqual(['data7', 'data8', 'data9'],
                         start_results['stuff_table']['Col1'])
        self.assertEqual(['0', '9', ' '], start_results['stuff_table']['Col2'])
        self.assertEqual(['data10', 'data11', 'data12'],
                         start_results['stuff_table']['Col3'])

        # ignore rows, space delimited
        table_test_ignore_rows = {
            'scheduler': 'raw',
            'build': {
                'source_path': 'tables.txt'
            },
            'run': {
                'cmds': [
                    'cat tables.txt'
                ]
            },
            'result_parse': {
                'table': {
                    'with_skip': {
                        'delimiter': ' ',
                        'col_num': '4',
                        'col_names': ['colA', 'colB', 'colC', 'colD'],
                        'start_re': r'^skip rows',
                        'row_ignore': ['2', '3', '6'],
                        'line_num': '9'
                    }
                }
            }
        }

        ignore_rows_test = self._quick_test(table_test_ignore_rows,
                                            'result_parser_test')
        ignore_rows_test.run()
        ignore_rows_results = {'pav_result_errors': []}
        parsers.parse_results(ignore_rows_test, ignore_rows_results)

        self.assertEqual(['item1', 'item5', 'item9', 'item13'],
                         ignore_rows_results['with_skip']['colA'])
        self.assertEqual(['item2', 'item6', 'item10', 'item14'],
                         ignore_rows_results['with_skip']['colB'])
        self.assertEqual(['item3', 'item7', 'item11', 'item15'],
                         ignore_rows_results['with_skip']['colC'])
        self.assertEqual(['item4', 'item8', 'item12', 'item16'],
                         ignore_rows_results['with_skip']['colD'])

        # start skip, row_nums, and with rows
        rows_and_cols = {
            'scheduler': 'raw',
            'build': {
                'source_path': 'tables.txt'
            },
            'run': {
                'cmds': [
                    'cat tables.txt'
                ]
            },
            'result_parse': {
                'table': {
                    'with_rows': {
                        'delimiter': ' ',
                        'col_num': '5',
                        'start_re': r'^start skip',
                        'has_header': 'True',
                        'start_skip': '2',
                        'col_names': [' ', 'col1', 'col2', 'col3', 'col4'],
                        'line_num': '4'
                    }
                }
            }
        }
        has_header_test = self._quick_test(rows_and_cols, 'result_parser_test')
        has_header_test.run()
        has_header_results = {'pav_result_errors': []}
        parsers.parse_results(has_header_test, has_header_results)

        self.assertEqual(3, len(has_header_results['with_rows'].keys()))
        self.assertEqual('1', has_header_results['with_rows']['r1']['col1'])
        self.assertEqual('6', has_header_results['with_rows']['r2']['col2'])
        self.assertEqual('10', has_header_results['with_rows']['r3']['col3'])

        # comma delimiter
        table_test3 = {
            'scheduler': 'raw',
            'run': {
                'cmds': [
                    'echo "----------- Comma-delimited summary ---------"',
                    'echo "./clomp_hwloc 4 -1 256 10 32 1 100, calc_deposit, OMP Barrier, Scaled Serial Ref, Bestcase OMP, Static OMP, Dynamic OMP, Manual OMP"',
                    'echo "Runtime,   0.000,   0.919,   2.641,   0.517,   2.345,  16.392,   2.324"',
                    'echo "us/Loop,    0.00,    9.41,   27.04,    5.29,   24.01,  167.85,   23.79"',
                    'echo "Speedup,     N/A,     N/A,    1.00,     5.1,     1.1,     0.2,     1.1"',
                    'echo "Efficacy,    N/A,     N/A,     N/A,   100%,   22.0%,    3.2%, 22.2%"',
                    'echo "Overhead,    N/A,     N/A,     N/A,    0.00,   18.72,  162.56,   18.50"',
                    'echo "CORAL2 RFP, 4 -1 256 10 32 1 100, 1.00, 27.04, 27.04, 9.41, 5.1, 18.72, 1.1, 162.56, 0.2, 18.50, 1.1"'
                ]
            },
            'result_parse': {
                'table': {
                    'table3': {
                        'delimiter': ',',
                        'col_num': '8',
                        'has_header': 'True',
                        'by_column': 'True',
                        'col_names': [
                            ' ', 'calc_deposit', 'OMP Barrier',
                            'Scaled Serial Ref', 'Bestcase OMP',
                            'Static OMP', 'Dynamic OMP', 'Manual OMP']
                    }
                }
            }
        }

        test = self._quick_test(table_test3, 'result_parser_test')
        test.run()

        results = {'pav_result_errors': []}
        result.parse_results(test, results, utils.IndentedLog())

        self.assertEqual('0.000', results['table3']['calc_deposit']['Runtime'])
        self.assertEqual('9.41', results['table3']['OMP Barrier']['us/Loop'])
        self.assertEqual('1.00',
                         results['table3']['Scaled Serial Ref']['Speedup'])
        self.assertEqual('100%', results['table3']['Bestcase OMP']['Efficacy'])
        self.assertEqual('18.72', results['table3']['Static OMP']['Overhead'])
        self.assertEqual('16.392', results['table3']['Dynamic OMP']['Runtime'])
        self.assertEqual('23.79', results['table3']['Manual OMP']['us/Loop'])

    def test_evaluate(self):

        ordered = OrderedDict()
        ordered['val_a'] = '3'
        ordered['val_b'] = 'val_a + 1'

        base_cfg = self._quick_test_cfg()
        base_cfg['run']['cmds'] = [
            'echo True > bool.out',
            'echo 1 > int.out',
            'echo 2.3 > float.out',
            'echo "blarg" > str.out',
        ]
        base_cfg['result_parse'] = {
            'regex': {
                'data': {
                    'regex': r'.*',
                    'per_file': 'name',
                    'files': '*.out',
                }
            }
        }

        # (evaluate_conf, expected values)
        evaluate_tests = [
            ({'result': 'True'}, {'result': 'PASS'}),
            ({'result': 'return_value != 0',
              'blarg': 'return_value != 0'}, {'result': 'FAIL'}),
            # Make sure functions work.
            ({'sum': 'sum([1,2,3])'}, {'sum': 6}),

            # Check basic math.
            ({'val_a': '3',
              'val_b': 'val_a + val_c',
              'val_c': 'val_a*2'},
             {'val_a': 3, 'val_b': 9, 'val_c': 6}),

            # Check list operations.
            ({'list_ops': '[1, 2, 3] == 2'},
             {'list_ops': [False, True, False]}),
            ({'type_conv': 'per_file.*.data'},
             # The order here should be consistent
             {'type_conv': [True, 2.3, 1, "blarg"]})
        ]

        for evaluate_conf, exp_results in evaluate_tests:

            cfg = copy.deepcopy(base_cfg)
            cfg['result_evaluate'] = evaluate_conf

            test = self._quick_test(cfg)
            test.run()

            results = test.gather_results(0)

            for rkey, rval in exp_results.items():
                self.assertEqual(
                    results[rkey],
                    exp_results[rkey],
                    msg="Result mismatch for {}.\n"
                        "Expected '{}', got '{}'\n"
                        "Full Results:\n{}"
                        .format(evaluate_conf, exp_results[rkey],
                                results[rkey], pprint.pformat(results)))

    def test_evaluate_errors(self):
        error_confs = (
            {'val_a': 'undefined_a'},  # No such variable
            {'val_b': 'parse_error ++'},  # Parse error
            {'val_c': '"hello" + 3'},  # Value Error
            {'val_d': 'val_e + 3', 'val_e': 'val_d + 1'},  # Reference loop.
            {'val_f': 'really.complicated.*.variable.error'}
        )

        for error_conf in error_confs:
            cfg = self._quick_test_cfg()
            cfg['result_evaluate'] = error_conf

            test = self._quick_test(cfg)
            test.run()

            with self.assertRaises(pavilion.result.common.ResultError):
                result.evaluate_results({}, error_conf, utils.IndentedLog())

    def test_result_cmd(self):
        """Make sure the result command works as expected, including the
        re-run option."""

        result_cmd = commands.get_command('result')
        result_cmd.silence()
        run_cmd = commands.get_command('run')  # type: run.RunCommand
        run_cmd.silence()

        rerun_cfg = self.pav_cfg.copy()
        rerun_cfg['config_dirs'] = [
            self.PAV_LIB_DIR,
            self.PAV_ROOT_DIR/'test/data/configs-rerun',
        ]

        arg_parser = arguments.get_parser()
        run_args = arg_parser.parse_args(['run', 'result_tests.*'])
        if run_cmd.run(self.pav_cfg, run_args) != 0:
            cmd_out, cmd_err = run_cmd.clear_output()
            self.fail("Run command failed: \n{}\n{}".format(cmd_out, cmd_err))

        for test in run_cmd.last_tests:
            test.wait(3)

        res_args = arg_parser.parse_args(
            ('result', '--full') + tuple(str(t.id) for t in run_cmd.last_tests))
        if result_cmd.run(self.pav_cfg, res_args) != 0:
            cmd_out, cmd_err = result_cmd.clear_output()
            self.fail("Result command failed: \n{}\n{}"
                      .format(cmd_out, cmd_err))

        res_args = arg_parser.parse_args(
            ('result',) + tuple(str(t.id) for t in run_cmd.last_tests))
        if result_cmd.run(self.pav_cfg, res_args) != 0:
            cmd_out, cmd_err = result_cmd.clear_output()
            self.fail("Result command failed: \n{}\n{}"
                      .format(cmd_out, cmd_err))

        for test in run_cmd.last_tests:
            # Each of these tests should have a 'FAIL' as the result.
            self.assertEqual(test.results['result'], TestRun.FAIL)

        # Make sure we can re-run results, even with permutations.
        # Check that the changed results are what we expected.
        result_cmd.clear_output()
        res_args = arg_parser.parse_args(
            ('result', '--re-run', '--json') +
            tuple(str(t.id) for t in run_cmd.last_tests))
        result_cmd.run(rerun_cfg, res_args)

        data, err = result_cmd.clear_output()
        results = json.loads(data)

        basic = results['result_tests.basic']
        per1 = results['result_tests.permuted.1']
        per2 = results['result_tests.permuted.2']

        self.assertEqual(basic['result'], TestRun.PASS)
        self.assertEqual(per1['result'], TestRun.FAIL)
        self.assertEqual(per2['result'], TestRun.PASS)

        # Make sure we didn't save any of the changes.
        orig_test = run_cmd.last_tests[0]
        reloaded_test = TestRun.load(self.pav_cfg, orig_test.id)
        self.assertEqual(reloaded_test.results, orig_test.results)
        self.assertEqual(reloaded_test.config, orig_test.config)

        # Make sure the log argument doesn't blow up.
        res_args = arg_parser.parse_args(
            ('result', '--show-log') +
            tuple(str(t.id) for t in run_cmd.last_tests))
        if result_cmd.run(self.pav_cfg, res_args) != 0:
            cmd_out, cmd_err = result_cmd.clear_output()
            self.fail("Result command failed: \n{}\n{}"
                      .format(cmd_out, cmd_err))

    def test_re_search(self):
        """Check basic re functionality."""

        answers = {
            'hello': '33',
            'ip': '127.33.123.43',
            'all_escapes': r'.^$*\+?\{}\[]|'
        }

        test = self._load_test('re_search')[0]
        test.run()

        results = test.gather_results(0)

        for key, answer in answers.items():
            self.assertEqual(results[key], answer)

    def test_constant_parser(self):
        """Check the constant parser."""

        cfg = self._quick_test_cfg()
        cfg['variables'] = {
            'foo': ['bar']
        }
        cfg['result_parse'] = {
            'constant': {
                'foo': {
                    'const': '{{foo}}',
                },
                'baz': {
                    'const': '33',
                }
            }
        }

        expected = {
            'foo': 'bar',
            'baz': 33,
        }

        test = self._quick_test(cfg, 'const_parser_test')
        test.run()
        results = test.gather_results(0)

        for key in expected:
            self.assertEqual(results[key], expected[key])

    def test_forced_parser_defaults(self):
        """Make sure we honor the result parser's FORCED_DEFAULTS."""

        cfg = self._quick_test_cfg()
        cfg['result_parse'] = {
            'constant': {
                'foo': {
                    'const': 'bar',
                    'preceded_by': 'unsettable',
                }
            }
        }

        with self.assertRaises(pavilion.result.common.ResultError):
            result.check_config(cfg['result_parse'], {})

        test = self._quick_test(cfg, 'split_test')
        test.run()
        results = test.gather_results(0)

        self.assertNotIn('foo', results)
        self.assertTrue(results[result.RESULT_ERRORS][0].endswith(
            "This parser requires that you not set the 'preceded_by' key, as "
            "the default value is the only valid option."
        ))

    def test_split_parser(self):
        """Check the split parser."""

        cfg = self._quick_test_cfg()

        cfg['run']['cmds'] = [
            'echo "Results1"',
            'echo " 1 1.2       hello "',
            'echo "Results2"',
            'echo "1, 3, 5, 9, blarg, 11"',
        ]

        cfg['result_parse'] = {
            'split': {
                'a1,b1,c1': {
                    'preceded_by': [r'Results1']
                },
                'a2, _, _, _, b2':      {
                    'sep': ',',
                    'preceded_by':        [r'Results2'],
                },
            }
        }

        expected = {
            'a1': 1,
            'b1': 1.2,
            'c1': 'hello',
            'a2': 1,
            'b2': 'blarg',
        }

        test = self._quick_test(cfg, 'split_test')
        test.run()
        results = test.gather_results(0)

        for key in expected:
            self.assertEqual(results[key], expected[key])

    def test_flatten_results(self):
        """Make sure result flattening works as expected, as well as regular
        result output while we're at it."""

        config = self._quick_test_cfg()

        config['run']['cmds'] = [
            'for i in 1 2 3 4; do echo "hello $i" > $i.out; done'
        ]
        config['result_parse']['regex'] = {
            'hello': {
                'regex':    r'hello \d+',
                'files':    '*.out',
                'per_file': 'name',
            }
        }

        test = self._quick_test(config, name="flatten_results_test1")

        run_result = test.run()
        results = test.gather_results(run_result)
        test.save_results(results)

        flattened = {}

        test2 = self._quick_test(config, name="flatten_results_test2")
        run_result = test2.run()
        results = test2.gather_results(run_result)
        test2._pav_cfg = test2._pav_cfg.copy()
        test2._pav_cfg['flatten_results'] = False
        test2.save_results(results)

        with self.pav_cfg['result_log'].open() as results_log:
            for line in results_log.readlines():
                _result = json.loads(line)

                # Reconstruct the per_file dict, so that flattened and
                # unflattened are the same. If there's a format error, this
                # will have problems.
                if _result['name'] == "unittest.flatten_results_test1":
                    flattened[_result['file']] = {'hello': _result['hello']}
                elif _result['name'] == "unittest.flatten_results_test2":
                    unflattened = _result['per_file']

        answer = {
            '1': {'hello': 'hello 1'},
            '2': {'hello': 'hello 2'},
            '3': {'hello': 'hello 3'},
            '4': {'hello': 'hello 4'},
        }

        self.assertEqual(flattened, answer)
        self.assertEqual(unflattened, answer)
