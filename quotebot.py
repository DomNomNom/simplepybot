from commandbot import *
import dbm

class QuoteDB:
    '''
    Trivial wrapper class over dbm to enable use in with statements.
    '''
    def __enter__(self):
        self._internal = dbm.open('quotes', 'c')
        return self._internal
    def __exit__(self, type, value, traceback):
        self._internal.close()

class QuoteBot(CommandBot):
    '''
    An IRC Bot that can store, retrieve, and delete items.

    Contains a simple easter egg - HONK.
    '''
    honk = "HONK"
    nick = "gamzee"
    def __init__(self, network, port):
        self.commands = [
            command(r"^%s:" % self.nick, self.honk),
            command(r"^!learn (?P<abbr>\S+) as (?P<long>\S.*)$", self.learn),
            command(r"^!forget (?P<abbr>\S+)", self.forget),
            command(r"^!(?P<abbr>\S+)$", self.retrieve)
        ]
        super(QuoteBot, self).__init__(self.nick, network, port)
        self.honk = "HONK"

    def alternate_honk(self):
        '''
        Alternate between HONK and honk.
        '''
        self.honk = self.honk.swapcase()
        return self.honk

    def honk(self, source, action, targets, message, m):
        '''
        Honk at anyone that highlighted us.
        '''
        self.msg_all(self.alternate_honk(), targets)

    def learn(self, source, action, targets, message, m):
        '''
        Learn a new abbreviation.
        '''
        self.msg_all('Remembering %s as %s' % (m.group('abbr'), m.group('long')), targets)
        self.quotes[m.group('abbr')] = m.group('long')

    def forget(self, source, action, targets, message, m):
        '''
        Forget about an abbreviation.
        '''
        command = m.group('abbr')
        if command in self.quotes:
            del(self.quotes[command])
            self.msg_all("Hrm. I used to remember %s. Now I don't." % command, targets)
        else:
            self.msg_all("Sorry, I don't about %s." % command, targets)

    def retrieve(self, source, action, targets, message, m):
        '''
        Retrieves a command.
        '''
        command = m.group('abbr')
        if command in self.quotes:
            self.msg_all("%s: %s" % (command, self.quotes[command].decode()), targets)
        else:
            self.msg_all("Sorry, I don't about %s." % command, targets)

    def loop(self):
        with QuoteDB() as self.quotes:
            super(QuoteBot, self).loop()

qb = QuoteBot("irc.segfault.net.nz", 6667)
qb.join("#bots")
qb.loop()