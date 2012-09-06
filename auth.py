json, logging, urllib
from google.appengine.api import users
from google.appengine.ext import db, webapp
import tweepy
import model

TWITTER_CONSUMER_KEY    = "FEcBCnl9EegBp63AHnfyQA"
TWITTER_CONSUMER_SECRET = "XvVir9WQqHpo1WnN1nIx8Bdc4FnlexzZ9lUAuPPHnzs"
FACEBOOK_APP_ID         = "492168570793246"
FACEBOOK_SECRET         = "2a66e1b04a737f46a265826885e1a5e7"

#OAuth registration
class RegisterTwitter(webapp2.RequestHandler):
        auth = tweepy.OAuthHandler(TWITTER_CONSUMER_KEY,
                                   TWITTER_CONSUMER_SECRET,
                                   "https://epubhost.appspot.com/auth/twitter/callback")

        try:
            redirect_url = auth.get_authorization_url()
            session.set("rt_key_", auth.request_token.key)
            session.set("rt_secret_", auth.request_token.secret)
            self.redirect(redirect_url)
        except tweepy.TweepError:
            self.response.out.write('Error! Failed to get request token.')

class TwitterCallback(webapp2.RequestHandler):
    def get(self):
        verifier = self.request.get('oauth_verifier')
        auth = tweepy.OAuthHandler(TWITTER_CONSUMER_KEY, TWITTER_CONSUMER_SECRET, secure=True)

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

        account = session.get("account")
        if account is None:
          account = model.Account().all().filter("twitterHandle = ?", twitter.auth.get_username()).get()
        if account is None:
          account = Account.new(
            twitterHandle = twitter.auth.get_username(),
            twitterToken = auth.access_token.secret)
        else:
          account.twitterHandle = twitter.auth.get_username()
          account.twitterToken = auth.access_token.secret

        account.put()
        self.response.out.write("Twitter registered.")

class RegisterFacebook(webapp2.RequestHandler):
    def get(self):
        args = dict(client_id=HFT_FACEBOOK_APP_ID,
                    redirect_uri="https://epubhost.appspot.com/auth/facebook/callback",
                    scope="email,user_about_me,user_education_history,user_interests,user_likes")
        self.redirect( "https://graph.facebook.com/oauth/authorize?" + urllib.urlencode(args))

class FacebookCallback(webapp2.RequestHandler):
    def get(self):
        args = dict(client_id=HFT_FACEBOOK_APP_ID, redirect_uri="https://epubhost.appspot.com/auth/facebook/callback")
        args["client_secret"] = HFT_FACEBOOK_SECRET
        args["code"] = self.request.get("code")
        response = cgi.parse_qs(urllib.urlopen(
            "https://graph.facebook.com/oauth/access_token?" +
            urllib.urlencode(args)).read())
        access_token = response["access_token"][-1]

        fbUID = "TODO"
        account = session.get("account")
        if account is None:
          account = model.Account().all().filter("facebookUID = ?", fbUID).get()
        if account is None:
          account = Account.new(facebookToken = access_token)
        else:
          account.facebookToken = access_token

        account.put()
        self.response.out.write("Facebook registered.")

app = webapp2.WSGIApplication([
    ('/auth/twitter', RegisterTwitter),
    ('/auth/twitter/callback', TwitterCallback),
    ('/auth/facebook', RegisterFacebook),
    ('/auth/facebook/callback', FacebookCallback),
    debug=True)

