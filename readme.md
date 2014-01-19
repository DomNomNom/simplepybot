Simplepybot is an attempt at a dead simple python irc bot

Right now it's written in python 2.7 but plans are in the works to port it to 3.x

The master head is likely to be broken most of the time, but I will list tagged versions that work, that you can check and use

* v0.1 - Stable, but lacks a lot of the latest features
* v0.2 - unstable, aliasbot module runs, has later features


In terms of a todo
* The current in progress work is to move all config into a dict of AttrDicts(see commandbot for this class). These config dicts will help simplify handling configuration (as well as let developers load config in any way they want, as long as they end up with the right final dict structure). It will also help with writing a module to modify configuration options at runtime, as the config structure will be known.

* Write a script that will autogenerate irc.py event_util.py and numerics.py from a json/txt file. This is all simply code that provides a wrapper over the event system simplepybot uses, it's entirely plausible that the bindings at each level can be programtically generated, preventing you having to write the same method basically twice

* Hook authentication module into the new identity map, so you can always refer to users by nick and have it use their hostname transparently

* Clean up logging, right now it's extremely spammy and I want to fix that by leaving most modules set on INFO and above level and only turn on DEBUG on modules that I am programming on explicitly, this is sort of in progress as part of the config work

* Clean up the modules to be in line with the new formats for bot work

* Perhaps provide some worker thread system for long running module commands that don't need to reference the main bot or data

* Reload the modules dynamically at runtime, this will let non core modules be developed without having to constantly stop and restart bot

* Name space commands so you can do either !command or !module.command if command is conflicting with another command

* Error handling cleanup and work

* Other stuff I have written down but not included here
