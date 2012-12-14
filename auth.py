import cgi, json, logging, urllib
from google.appengine.api import users
from google.appengine.ext import db, webapp
from gaesessions import get_current_session
import tweepy
import model

TWITTER_CONSUMER_KEY    = "FEcBCnl9EegBp63AHnfyQA"
TWITTER_CONSUMER_SECRET = "XvVir9WQqHpo1WnN1nIx8Bdc4FnlexzZ9lUAuPPHnzs"
FACEBOOK_APP_ID         = "492168570793246"
FACEBOOK_SECRET         = "2a66e1b04a737f46a265826885e1a5e7"

#OAuth registration
class RegisterTwitter(webapp.RequestHandler):
    def get(self):
        auth = tweepy.OAuthHandler(TWITTER_CONSUMER_KEY,
                                   TWITTER_CONSUMER_SECRET,
                                   "http://www.epubhost.com/auth/twitter/callback")

        try:
            redirect_url = auth.get_authorization_url()
            session = get_current_session()
            session["rt_key_"] = auth.request_token.key
            session["rt_secret_"] = auth.request_token.secret
            self.redirect(redirect_url)
        except tweepy.TweepError:
            self.response.out.write('Error! Failed to get request token.')

class TwitterCallback(webapp.RequestHandler):
    def get(self):
        verifier = self.request.get('oauth_verifier')
        auth = tweepy.OAuthHandler(TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET, secure=True)

        session = get_current_session()
        request_key = session.get("rt_key_")
        request_secret = session.get("rt_secret_")
        if request_key is None or request_secret is None:
            self.response.out.write('Error! Failed to retain account/handle or request key/secret.')
            return

        auth.set_request_token(request_key, request_secret)
        try:
            auth.get_access_token(verifier)
        except tweepy.TweepError:
            self.response.out.write('Error! Failed to get access token.')
            return

        auth.set_access_token(auth.access_token.key, auth.access_token.secret)
        twitter = tweepy.API(auth)
        twitterUsername = twitter.auth.get_username()

        account = db.GqlQuery("SELECT * FROM Account WHERE twitterHandle = :1", twitterUsername).get()
        if account is None:
            account_key = session.get("account")
            account = None if account_key is None else db.get(account_key)
        if account is None:
            account = model.Account()
        account.twitterHandle = twitterUsername
        account.twitterKey = auth.access_token.key
        account.twitterToken = auth.access_token.secret

        account.put()
        session["account"] = account.key()
        self.redirect("/")

class RegisterFacebook(webapp.RequestHandler):
    def get(self):
        args = dict(client_id=FACEBOOK_APP_ID,
                    redirect_uri="http://www.epubhost.com/auth/facebook/callback",
                    scope="email")
        self.redirect( "https://graph.facebook.com/oauth/authorize?" + urllib.urlencode(args))

class FacebookCallback(webapp.RequestHandler):
    def get(self):
        args = dict(client_id=FACEBOOK_APP_ID, redirect_uri="http://www.epubhost.com/auth/facebook/callback")
        args["client_secret"] = FACEBOOK_SECRET
        args["code"] = self.request.get("code")
        response = cgi.parse_qs(urllib.urlopen(
            "https://graph.facebook.com/oauth/access_token?" +
            urllib.urlencode(args)).read())
        access_token = response["access_token"][-1]

        session = get_current_session()

        me = urllib.urlopen("https://graph.facebook.com/me?access_token="+access_token).read()
        fbData = json.loads(me)
        fbUID = fbData["id"]

        account = db.GqlQuery("SELECT * FROM Account WHERE facebookUID = :1", fbUID).get()
        if account is None:
            account_key = session.get("account")
            account = None if account_key is None else db.get(account_key)
        if account is None:
            account = model.Account()

        account.facebookToken = access_token
        account.facebookUID = fbUID
        try:
            account.facebookInfo = json.dumps(fbData)
            account.facebookInterests = urllib.urlopen("https://graph.facebook.com/me/interests?access_token="+access_token).read()
        except Exception, ex:
            logging.info("Couldn't get/save FB data due to %s" % ex)
        account.put()

        session["account"] = account.key()
        self.redirect("/")

app = webapp.WSGIApplication([
    ('/auth/twitter', RegisterTwitter),
    ('/auth/twitter/callback', TwitterCallback),
    ('/auth/facebook', RegisterFacebook),
    ('/auth/facebook/callback', FacebookCallback),
    ],
    debug=True)

