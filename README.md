epubhost
========

A Python-on-App-Engine service that lets people store, search, and share quotes from DRM-free ebooks.

http://www.epubhost.com/

Whole bunch of stuff I'd like to do, eg extend support to DRM-free Kindle books (yes, they do exist!),
cache books locally via HTML5 for mobile reading, share quotes to FB/Twitter, add some unit tests, etc.

Hopefully useful as an example of an App Engine site written in Python that includes use of background tasks,
the BigTable datastore, Google's full-text Search API, etc.

I did make a cursory check for existing libraries and didn't find anything that quite seemed to fit
(other than Tweepy, and GAESessions, which should really be git submodules here),
but I expect there are several that I could and should have used...

Note that only Creative Commons and Public Domain books are publicly available
(and I'm the only one who verifies what's CC and PD) in order to avoid rights violations.

I expect there's the odd bug, too, and notifications of such would be welcome, as are pull requests.
