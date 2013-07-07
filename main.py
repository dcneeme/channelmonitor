import android
import os
import time
droid = android.Android()

APPDIR='/sdcard/sl4a/scripts/d4c/' # trailing slash needed

#if os.path.isdir('pymodbus') and os.path.isdir('requests'): # only use pymodbus if the module can be loaded
try:
    import pymodbus  # these modules can also be elsewhere!
    import requests
    STARTUP_SCRIPTS = ['channelmonitor_pm.py','webserver.py'] # using pymodbus and requests
    print 'starting using pymodbus'
except:
    STARTUP_SCRIPTS = ['channelmonitor3.py','webserver.py'] # not using pymodbus
    print 'starting without pymodbus'
    

msg='starting'
droid.ttsSpeak(msg)
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