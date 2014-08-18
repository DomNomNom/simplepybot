from commandbot import *
import sys
import logging
import logging.handlers as handlers

class AliasBot:
    '''
    An IRC Bot that can store, retrieve, and delete items.
    This bot stands as the simplest example of how to use
    the framework
    Contains a simple easter egg - HONK.
    '''
    def __init__(self, bot, config):
        #set up logging
        self.config = config
        self.log = logging.getLogger(self.config.module_name)
        self.log.setLevel(self.config.log_level)
        if self.config.log_handlers:
            for handler in self.config.log_handlers:
                self.log.addHandler(handler)

        self.commands = [
                bot.command(r"^\w*", self.honk, direct=True),
                bot.command(r"^!learn (?P<abbr>\S+) as (?P<long>.+)$", self.learn, auth_level = 20),
                bot.command(r"^!forget (?P<abbr>\S+)", self.forget, auth_level = 20),
                bot.command(r"^!list_abbr$", self.list_abbrievations, private=True),
                bot.command(r"^!(?P<abbr>\S+)$", self.retrieve)
                ]

        self.events = []

        self.bot = bot
        #Custom honk output
        if not self.config.honk:
            self.config.honk = "HONK"
        self.irc = bot.irc
        #get a reference to the bot database
        self.db = bot.db
        #set up a table for the module
        self.db.execute('CREATE TABLE IF NOT EXISTS {0} (short text UNIQUE NOT NULL, long text NOT NULL)'.format(self.config.module_name))
        #register as a module
        bot.add_module(module_name, self)

        self.log.info(u'Finished intialising {0}'.format(module_name))

    def alternate_honk(self):
        '''
        Alternate between HONK and honk.
        '''
        self.config.honk = self.config.honk.swapcase()
        return self.config.honk

    def honk(self, nick, nickhost, action, targets, message, m):
        '''
        Honk at anyone that highlighted us.
        '''
        self.irc.msg_all(self.alternate_honk(), targets)

    def learn(self, nick, nickhost, action, targets, message, m):
        '''
        Learn a new abbreviation.
        '''
        abbr = m.group('abbr')
        long_text = m.group('long')
        self.log.debug(u"Remembering {0} as {1}".format(abbr, long_text))

        try:
            self.db.execute('INSERT OR REPLACE INTO {0} VALUES (?, ?)'.format(self.config.module_name), [abbr, long_text])
            self.db.commit()
            self.irc.msg_all(u'Remembering {0} as {1}'.format(abbr, long_text), targets)

        except sqlite3.Error as e:
            self.log.exception(u'Could not change/add {0} as {1}'.format(abbr, long_text))
            self.db.rollback()
            self.irc.msg_all(u'Could not change/add {0} as {1}'.format(abbr, long_text), targets)

    def forget(self, nick, nickhost, action, targets, message, m):
        '''
        Forget about an abbreviation.
        '''
        abbr = m.group('abbr')
        self.log.debug(u"Forgetting {0}".format(abbr))
        try:
            if self.does_exist(abbr):
                self.db.execute('DELETE FROM {0} WHERE short = ?'.format(self.config.module_name), [abbr])
                self.db.commit()
                self.irc.msg_all(u'Successfully deleted {0} from database'.format(abbr), targets)

            else:
                self.irc.msg_all(u'{0} is not in the database'.format(abbr), targets)

        except sqlite3.Error as e:
            self.log.exception(u'Unable to delete {0}'.format(abbr))
            self.irc.msg_all(u'Unable to delete {0}'.format(abbr), targets)

    def retrieve(self, nick, nickhost, action, targets, message, m):
        '''
        Retrieves a long version of an abbrievated nick
        '''
        abbr = m.group('abbr')
        self.log.debug(u"Retrieving {0}".format(abbr))
        try:
            result = self.db.execute('SELECT long FROM {0} WHERE short = ?'.format(self.config.module_name), [abbr]).fetchone()
            if result:
                result = result[0]
                self.irc.msg_all(str(result), targets)

            else:
                pass
                #self.irc.msg_all('No result for abbrievation {0}'.format(abbr), targets)

        except sqlite3.Error as e:
            self.log.exception(u"Unable to retrieve {0}".format(abbr))
            self.irc.msg_all(u'Unable to retrieve {0}'.format(abbr), targets)


    def list_abbrievations(self, nick, nickhost, action, targets, message, m):
        """
        List all known abbrievation commands
        """
        try:
            results = self.db.execute('SELECT * FROM {0}'.format(self.config.module_name)).fetchall()
            if results:
                self.irc.msg_all(u",".join(map(str, results)), targets)

            else:
                self.irc.msg_all(u'No stored abbrievations yet', targets)

        except sqlite3.Error as e:
            self.log.exception(u"Unable to retrieve abbrievations")
            self.irc.msg_all(u"Unable to retrieve abbrievations", targets)

    def does_exist(self, abbr):
        '''
        Returns true if the item with abbr exist in the database
        If it does not it returns false
        '''
        self.log.debug(u"Testing if {0} exists".format(abbr))
        try:
            result = self.db.execute('SELECT * FROM {0} WHERE short = ?'.format(self.config.module_name), [abbr]).fetchone()
            if result:
                self.log.debug(u"It Does")
                return True

            else:
                self.log.debug(u"It doesn't")
                return False

        except sqlite3.Error as e:
            self.log.exception(u'Could not verify {0} exists'.format(abbr))
            return False

    def close(self):
        #we don't do anything special
        pass

if __name__ == '__main__':
    #basic stream handler
    h = logging.StreamHandler()
    h.setLevel(logging.INFO)
    #format to use
    f = logging.Formatter(u"%(name)s %(levelname)s %(message)s")
    h.setFormatter(f)
    f_h= handlers.TimedRotatingFileHandler("bot.log", when="midnight")
    f_h.setFormatter(f)
    f_h.setLevel(logging.DEBUG)
    config = dict()

    #configure core
    coreconfig = new AttrDict()
    coreconfig.nick = 'arsenic2'
    coreconfig.server = 'irc.segfault.net.nz'
    coreconfig.port = 6667
    coreconfig.log_handlers = [h, f_h]
    coreconfig.log_level = logging.DEBUG
    config['core'] = coreconfig;

#configure auth
    authconfig = new AttrDict()
    authconfig.log_handlers = [h, f_h]
    authconfig.module_name = ['auth_host']
    authconfig.log_level = logging.DEBUG
    config[authconfig.module_name] = authconfig

    #configure aliasbot
    aliasconfig = new AttrDict()
    aliasconfig.log_handlers = [h, f_h]
    aliasconfig.log_level = logging.DEBUG

    bot = CommandBot('arsenic2', 'irc.segfault.net.nz', 6667, log_handlers=[h, f_h])
    mod = AliasBot(bot, aliasconfig)
    bot.join('#bots')
    bot.loop()
