from commandbot import *

class LogBot(CommandBot):
    """
    An IRC bot that can remember up to 100 messages in any channel
    and offers log searching services
    
    Written as a runup to quotebot and to test command bots builtin
    logging features
    """
    nick = "LumberJack"
    def __init__(self, network, port):
        self.commands = [
                command(r"^%s: quit" % self.nick, self.end),
                command(r"^!harvest (?P<match>.*)", self.harvest)
                ]
        super(LogBot, self).__init__(self.nick, network, port)



    def harvest(self, source, actions, targets, message, m):
        """
        Search the logs for anything matching the m.group("match") value
        """
        if m.group("match"):
            try:
                result = self.search_logs(m.group("match"), match=False)
                if result:
                    message = "Harvested:{0}, sender:{1}".format(result[2], result[0])
                    self.msg_all(message, targets)

                else:
                    self.msg_all("No match found", targets)

            except re.error:
                self.msg_all("Not a valid regex", targets)


    def end(self, source, actions, targets, message, m):
        """
        Quit server and kill script
        """
        self.quit("I might try some woman's clothing")
        sys.exit(0)

hb = LogBot("irc.segfault.net.nz", 6667)
hb.join("#bots")
hb.loop()

