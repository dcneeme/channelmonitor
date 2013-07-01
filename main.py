# this could be modified to be used in order to avoid any scripts running and restaerting on android phone during tests from linux
# BUT you can stop scripts running on android after you've started something on linux - if rs485 traffic is there, no restart will happen!
 
import android
import time

STARTUP_SCRIPTS = (
  'channelmonitor_pm.py',
  'webserver.py'
)

droid = android.Android()

msg='USB ON' # RUNNING, STARTING THE SCRIPTS'
#droid.makeToast(msg)
#droid.ttsSpeak(msg)
#time.sleep(1)
  
for script in STARTUP_SCRIPTS:
  extras = {"com.googlecode.android_scripting.extra.SCRIPT_PATH":"/sdcard/sl4a/scripts/d4c/%s" % script}
  myintent = droid.makeIntent("com.googlecode.android_scripting.action.LAUNCH_BACKGROUND_SCRIPT", None, None, extras, None, "com.googlecode.android_scripting", "com.googlecode.android_scripting.activity.ScriptingLayerServiceLauncher").result
  droid.startActivityIntent(myintent)
  msg='starting '+script
  droid.makeToast(msg)
  time.sleep(2)
  

# open web page(s) 
#droid.startActivity('android.intent.action.VIEW', 'http://www.itvilla.ee:80')
time.sleep(10)
droid.startActivity('android.intent.action.VIEW', 'http://127.0.0.1:8080/')