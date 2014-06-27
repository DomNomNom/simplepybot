from network import Network
import shelve
import sys
import re
import sqlite3
from datetime import datetime, timedelta
import time
import logging
import event_util as eu
import Queue
import threading
from authentication import IdentAuth
from ircmodule import IRC_Wrapper
import numerics as nu
from ident import IdentHost
from identcontrol import IdentControl

'''
A dictionary that acts kinda like a class
This wizardry is from
http://stackoverflow.com/questions/4984647/accessing-dict-keys-like-an-attribute-in-python
Will cause a memory leak in versions lower <2.7.3 and <3.2.3

We use it for the config, for a nicer way to access things
'''
class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs) #This calls all dict instantiation code
        self.__dict__ = self #So that this line is a valid call

class CommandBot():
    '''
    A simple IRC bot with command processing, event processing and timed event functionalities
    A framework for adding more modules to do more complex stuff
    '''

    def __init__(self, config, module_name='core', authmodule=None, ircmodule=None, identmodule=None):
        '''
        Create a new ircbot framework
        config is a mapping of module_name => AttrDict, that has config for each module
        module_name is the module name, and is also used to get the appropriate config dict
        authmodule - optional override of the authentication module the bot uses
        ircmodule -optional override of the irc wrapper the bot uses
        identmodule - optional override of the identity/channel mapper the bot uses
        '''

        self.modules = {}
        #store all the config
        self.all_config = config
        #get our config AttrDict out
        self.config = config[self.module_name]
        self.config.module_name = self.module_name
        self.log = logging.getLogger(self.config.log_name)
        self.log.setLevel(self.config.log_level)

        #if handlers were given we need to add them
        if log_handlers:
            for handler in self.config.log_handlers:
                self.log.addHandler(handler)

        #set up network stuff
        #IO queues
        self.inq = Queue.PriorityQueue()
        self.outq = Queue.PriorityQueue()
        #Set up network class
        net = Network(self.inq, self.outq, self.config.log_name)
        #Despatch the thread
        self.log.debug('Dispatching network thread')
        thread = threading.Thread(target=net.loop)
        thread.start()
        #network stuff done

        #tracker for if we are actually running
        #TODO what is this for?
        self.is_running=True

        #create a ref to the db connection
        self.db = sqlite3.connect(self.config.db_file)

        #irc wrapper bootstrapped before auth and ident, as they both require it
        if not ircmodule:
            self.irc = IRC_Wrapper(self, self.all_config)

        else:
            self.irc = ircmodule(self, self.all_config)

        if not identmodule:
            self.ident = IdentHost(self, self.all_config)#set up ident
            self.identcontrol = IdentControl(self, self.all_config) # module for controlling it

        else:
            self.ident = identmodule(self, self.all_config)

        #if no authmodule is passed through, use the default host/ident module
        if not authmodule:
            self.auth = IdentAuth(self, self.all_config)

        else:
            self.auth = authmodule(self, self.all_config)

        self.commands = [
                self.command("quit", self.end, direct=True, auth_level=20),
                self.command("mute", self.mute, direct=True, can_mute=False,
                             auth_level=20),
                self.command(r"!syntax ?(?P<module>\S+)?", self.syntax)
                ]
        #TODO I need to catch 441 or 436 and handle changing bot name by adding
        #a number or an underscore
        #catch also a 432 which is a bad uname

        self.events = [
                eu.event(nu.RPL_ENDOFMOTD, self.registered_event),
                eu.event(nu.ERR_NOMOTD, self.registered_event),
                eu.event(nu.BOT_ERR, self.reconnect),
                eu.event(nu.BOT_KILL, self.reconnect),
                eu.event(nu.BOT_PING, self.ping),
                #TODO: can get privmsg handling as an event?
                #self.event("PRIVMSG", self.handle_priv),
                ]

        self.timed_events = []

        #send out events to connect and send USER and NICK commands
        self.irc.connect(self.config.network, self.config.port)
        self.irc.user(self.config.nick, "Python Robot")
        self.irc.nick(self.config.nick)

    def command(self, expr, func, direct=False, can_mute=True, private=False,
                auth_level=100):
        '''
        Helper function that constructs a command handler suitable for CommandBot.
        Theres are essentially an extension of the EVENT concept from message_util.py
        with extra arguments and working only on PRIVMSGS

        args:
            expr - regex string to be matched against user message
            func - function to be called upon a match

        kwargs:
            direct - this message eust start with the bots nickname i.e botname
                     quit or botname: quit
            can_mute - Can this message be muted?
            private - Is this message always going to a private channel?
            auth_level - Level of auth this command requires (users who do not have
                         this level will be ignored

        These are intended to be evaluated against user messages and when a match is found
        it calls the associated function, passing through the match object to allow you to
        extract information from the command
        '''
        guard = re.compile(expr)
        def process(source, action, args, message):
            #grab nick and nick host
            nick, nickhost = source.split("!")

            #unfortunately there is weirdness in irc and when you get addressed in
            #a privmsg you see your own name as the channel instead of theirs
            #It would be nice if both sides saw the other persons name
            #so we replace any instance of our nick with their nick
            for i, channel in enumerate(args[:]):
                if channel == self.config.nick:
                    args[i] = nick

            #make sure this message was prefixed with our bot username
            if direct:
                if not message.startswith(self.config.nick):
                    return False

                #strip nick from message
                message = message[len(self.config.nick):]
                #strip away any syntax left over from addressing
                #this may or may not be there
                message = message.lstrip(": ")

            #If muted, or message private and the message can be muted
            #then send it direct to user via pm
            if (self.config.is_mute or private) and can_mute:
                #replace args with usernick stripped from source
                args = [nick]

            #check it matches regex and grab the matcher object so the function can
            #pull stuff out of it
            m = guard.match(message)
            if not m:
                return False

            '''
            auth_level < 0 means do no auth check at all!, this differs from the default
            which gives most things an auth_level of 100. The only thing that currently uses
            it is the auth module itself, for bootstrapping authentication. Not recommened for
            normal use as people may want ignore people who are not in the auth db, and they
            will change how level 100 checks are managed
            '''
            if auth_level:
                if auth_level > 0 and not bot.auth.is_allowed(nick, nickhost, auth_level):
                    return True #Auth failed but was command

            #call the function
            func(nick, nickhost, action, args, message, m)
            return True

        return process

    def in_event(self, event):
        self.inq.put(event)

    def out_event(self, event):
        self.outq.put(event)

    def add_module(self, name, module):
        '''
        Add the given module to the modules dictionary under the given name
        Raises a key error if the name is already in use
        '''
        if name in self.modules:
            raise KeyError(u"Module name:{0} already in use".format(name))
        self.modules[name] = module

    def get_module(self, name):
        '''
        Returns the module stored in module dict under the key given by name
        Raises a key error if there is no module with that name
        '''
        if name not in self.modules:
            raise KeyError(u"No module with the name:{0}".format(name))
        return self.modules[name]

    def has_module(self, name):
        '''
        Returns true if the bot has this module or false otherwise
        '''
        if name not in self.modules:
            return False
        else:
            return True

    def run_event_in(self, seconds, func, func_args=(), func_kwargs={}):
        '''
        Helper function that runs an event x seconds in the future, where seconds
        is how many seconds from now to run it
        '''
        start_time = datetime.now()
        interval = timedelta(seconds=seconds)
        end_time = start_time + interval
        self.add_timed_event(start_time, end_time, interval, func, func_args, func_kwargs)

    def add_timed_event(self, start_time, end_time, interval, func, func_args=(), func_kwargs={}):
        '''
        Add an event that will trigger once at start_time and then every time
        interval amount of time has elapsed it will trigger again until end_time
        has passed

        Start time and end time are datetime objects
        and interval is a timedelta object
        '''
        t_event = eu.TimedEvent(start_time, end_time, interval, func, func_args, func_kwargs)
        self.timed_events.append(t_event)

    def loop(self):
        '''
        Primary loop.
        You'll need to transfer control to this function before execution begins.
        '''
        while self.config.is_running:
            self.logic()
            time.sleep(.1)

        #clean up things after all modules have closed
        self.cleanup()
        self.log.info("Bot ending")

    def logic(self):
        '''
        Simple logic processing.

        Examines all messages received, then attempts to match commands against any messages, in 
        the following order

        if a privmsg
            commands local to commandbot
            commands in modules loaded

        all messages(including privmsgs)
        events local to commandbot
        events in modules loaded

        It also evaluates all timed events and triggers them appropriately
        '''
        try:
            #try to grab an event from the inbound queue
            m_event = self.inq.get(False)
            self.log.debug(u'Inbound event {0}'.format(m_event))
            was_event = False
            #if a priv message we first pass it through the command handlers
            if m_event.type == nu.BOT_PRIVMSG:
                was_event=True
                #unpack the data!
                action, source, args, message = m_event.data
                for command in self.commands:
                    try:
                        if command(source, action, args, message):
                            action = nu.BOT_COMM #we set the action to command so valid commands can be identified by modules
                            break

                    except Exception as e:
                        self.log.exception(u'Error in bot command handler')
                        self.irc.msg_all(u'I experienced an error', args)

                for module_name in self.modules:
                    module = self.modules[module_name]
                    for command in module.commands:
                        try:
                            if command(source, action, args, message):
                                action = nu.BOT_COMM
                                break

                        except Exception as e:
                            self.log.exception(u'Error in module command handler:{0}'.format(module_name))
                            self.irc.msg_all(u'{0} experienced an error'.format(module_name), args)

            #check it against the event commands
            for event in self.events:
                try:
                    if event(m_event):
                        was_event = True

                except Exception as e:
                    self.log.exception(u'Error in internal event handler')

            for module_name in self.modules:
                module = self.modules[module_name]
                for event in module.events:
                    try:
                        if event(m_event):
                            was_event = True

                    except Exception as e:
                        self.log.exception(u'Error in module event handler: {0}'.format(module_name))

            if not was_event:
                self.log.info(u'Unhandled event {0}'.format(m_event))

        except Queue.Empty:
            #nothing to do
            pass

        #clone timed events list and go through the clone
        for event in self.timed_events[:]:
            if event.should_trigger():
                try:
                    event.func(*event.func_args, **event.func_kwargs)

                except Exception as e:
                    self.log.exception(u'Error in timed event handler')

            if event.is_expired():
                #remove from the original list
                self.timed_events.remove(event)

        return

    def end(self, nick, nickhost, action, targets, message, m):
        '''
        End this bot, closing each module and quitting the server
        '''
        self.log.info(u'Shutting down bot')
        for name in self.modules:
            module = self.modules[name]
            try:
                module.close()
            except AttributeError as e:
                self.log.warning(u'Module {0} has no close method'.format(name))

        self.irc.quit(u'Bot has been terminated by {0}'.format(nick))#send quit msg to server
        self.irc.kill() # tell the network thread to shutdown
        self.config.is_running=False

    def cleanup():
        '''
        Cleanup any remaining things now that all modules are closed
        Currently used to close db
        '''
        self.db.close()

    def mute(self, nick, nickhost, action, targets, message, m):
        '''
        mute/unmute the bot
        '''
        self.config.is_mute = not self.config.is_mute

        if self.config.is_mute:
            message = u'Bot is now muted'

        else:
            message = u'Bot is now unmuted'

        self.irc.msg_all(message, targets)

    def registered_event(self, source, action, args, message):
        '''
        this is called when a MOTD or NOMOTD message gets received
        any actions that require you to be registered with
        name and nick first are cached and then called when
        this event is fired, for example, joining channels
        '''
        #TODO: what else do we need to extend this too?
        #messages/privmsgs
        self.config.registered = True
        for channel in self.channels:
            self.join(channel)

    def join(self, channel):
        if self.config.registered:
            #send join event
            self.irc.join(channel)
            #tell the ident module we joined this channel
            self.ident.join_channel(channel)
            if not(channel in self.channels):
                self.channels.append(channel)
        else:
            self.channels.append(channel)

    def reconnect(self, source, event, args, message):
        '''
        Handles disconnection by trying to reconnect 3 times
        before quitting
        '''
        #if we have been kicked, don"t attempt a reconnect
        if  event == nu.BOT_KILL:
            self.log.info(u'No reconnection attempt due to being killed')
            self.close()

        self.log.error(u'Lost connection to server:{0}'.format(message))
        if self.config.times_reconnected >= self.config.max_reconnects:
            self.log.error(u'Unable to reconnect to server on final retry attempt')
            self.close()

        else:
            self.log.info(u'Sleeping before reconnection attempt, {0} seconds'.format(self.times_reconnected*60))
            time.sleep((self.config.times_reconnected+1)*60)
            self.config.registered = False
            self.log.info(u'Attempting reconnection, attempt no: {0}'.format(self.times_reconnected))
            self.config.times_reconnected += 1
            #set up events to connect and send USER and NICK commands
            self.irc.connect(self.config.network, self.config.port)
            self.irc.user(self.config.nick, 'Python Robot')
            self.irc.nick(self.config.nick)

    def ping(self, source, action, args, message):
        '''
        Called on a ping and responds with a PONG
        '''
        self.irc.pong(message)
