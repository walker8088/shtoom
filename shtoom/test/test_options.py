# Copyright (C) 2004 Anthony Baxter
"""Tests for shtoom.app.Options
"""

import shtoom.Options as O

from twisted.trial import unittest

class OptionsTests(unittest.TestCase):

    def test_optionCreation(self):
        # basic test of option creation
        all = O.AllOptions()
        for gnum, gname in [ (x, 'Group%d'%x) for x in range(10) ]:
            group = O.OptionGroup(gname, 'This is %s'%gname)
            group.addOption(O.StringOption('string%d'%(gnum),
                                        'this is string option %d'%gnum))
            group.addOption(O.BooleanOption('bool%d'%(gnum),
                                        'this is boolean option %d'%gnum))
            group.addOption(O.NumberOption('num%d'%(gnum),
                                        'this is number option %d'%gnum))
            all.addGroup(group)
        self.assertEquals(len(list(all)), 10)
        self.assertEquals(len(list(list(all)[0])),3)
        self.assertEquals(len(list(list(all)[-1])),3)

    def test_duplicateOptions(self):
        all = O.AllOptions()
        group = O.OptionGroup('testgroup', 'this is a test group')
        group.addOption(O.StringOption('test1', 'this is test1'))
        group.addOption(O.StringOption('test2', 'this is test2'))
        # XXX This should fail with a DuplicateOptionError, but doesn't
        group.addOption(O.StringOption('test1', 'this is a duplicate test1'))
        all.addGroup(group)
        group2 = O.OptionGroup('testgroup', 'this is a duplicate')
        # XXX This should fail with a DuplicateOptionError, but doesn't
        all.addGroup(group2)
        group3 = O.OptionGroup('testgroup2', 'a second group')
        group3.addOption(O.StringOption('test1', 'this is a duplicate test1'))
        # XXX This should fail with a DuplicateOptionError, but doesn't
        all.addGroup(group3)

    def test_booleanOptions(self):
        pass

    def test_stringOptions(self):
        pass

    def test_choiceOptions(self):
        pass

    def test_numberOptions(self):
        pass

    def test_mergeOptions(self):
        pass

    def test_emitConfigParser(self):
        pass

    def test_loadConfigParser(self):
        pass

    def test_updateOptions(self):
        pass

    def test_dynamicUpdate(self):
        # Test that dynamically created options aren't saved to the option
        # file. We round-trip through ConfigParser to be sure
        ae = self.assertEquals
        all = O.AllOptions()
        g = O.OptionGroup('group','test group')
        g.addOption(O.StringOption('optiona', 'option - a', default='first'))
        g.addOption(O.StringOption('optionb', 'option - b', default='second'))
        # no default value
        g.addOption(O.StringOption('optionc', 'option - c'))
        all.addGroup(g)
        s1, s2, s3 = g
        cfg = _getConfigParsed(all)
        ae(cfg.sections(), [])
        ae(all.getValue('optiona'), 'first')
        ae(all.getValue('optionb'), 'second')
        ae(all.getValue('optionc'), O.NoDefaultOption)

        for g in all:
            s1, s2, s3 = g
            s2.setValue('hello')
        cfg = _getConfigParsed(all)
        ae(cfg.sections(), ['group'])
        opts = cfg.options('group') 
        opts.sort()
        ae(opts, ['optionb'])
        ae(cfg.get('group', 'optionb'), 'hello')
        s1.setValue('goodbye')

        all.setValue('optiona', 'testing')
        cfg = _getConfigParsed(all)
        ae(cfg.get('group', 'optiona'), 'testing')

        all.setValue('optionb', 'dosave')
        cfg = _getConfigParsed(all)
        opts = cfg.options('group') 
        opts.sort()
        ae(opts, ['optiona','optionb'])
        ae(cfg.get('group', 'optionb'), 'dosave')

        all.setValue('optionb', 'dontsave', dynamic=True)
        cfg = _getConfigParsed(all)
        ae(cfg.options('group'), ['optiona',])


    def test_optparse_generation(self):
        # Test the optparse parser created by an AllOptions object is sane
        pass

def _getConfigParsed(all):
    from ConfigParser import ConfigParser
    from StringIO import StringIO
    str = StringIO()
    c = all.emitConfigParser()
    str.write(c)
    str.seek(0)
    cfg = ConfigParser()
    cfg.readfp(str)
    return cfg
