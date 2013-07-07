import android
import os
import time

APPDIR='/sdcard/sl4a/scripts/d4c/' # trailing slash needed

#STARTUP_SCRIPTS = ['channelmonitor3.py','webserver.py']
STARTUP_SCRIPTS = ['channelmonitor_pm.py','webserver.py']

droid = android.Android()

msg='starting the application'
#droid.ttsSpeak(msg)
#droid.makeToast(msg)
#time.sleep(1)

for script in STARTUP_SCRIPTS:
  if '.py' in script and os.stat(APPDIR+script)[6] > 0: # file to execute exists
    extras = {"com.googlecode.android_scripting.extra.SCRIPT_PATH":APPDIR+"%s" % script}
    myintent = droid.makeIntent("com.googlecode.android_scripting.action.LAUNCH_BACKGROUND_SCRIPT", None, None, extras, None, "com.googlecode.android_scripting", "com.googlecode.android_scripting.activity.ScriptingLayerServiceLauncher").result
    droid.startActivityIntent(myintent)
    msg='starting '+script
  else:
    msg='No such py script - '+script

  droid.makeToast(msg)
  time.sleep(1)
  

# open web page(s)
#droid.startActivity('android.intent.action.VIEW', 'http://www.itvilla.ee:80')
#time.sleep(5)
#droid.startActivity('android.intent.action.VIEW', 'http://127.0.0.1:8080/')