-- android seadme setup tabel, baasi modbus_channels. systeem sama nagu barioneti muutujatega!
-- kindlasti vaja anda mon serverid, max teavitusintervall, obj nimetus jne

PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE setup(register,value,ts,desc,comment); -- desc jaab UI kaudu naha,  comment on enda jaoks. ts on muutmise aeg s

-- INSERT INTO 'setup' VALUES('S100','/sdcard/sl4a/acomm/py/channelmonitor3.py','','main loop script','main script to execute'); -- ei kasuta, votab main.py seest
-- wlan mac values below will ONLY be used if no mac can be read from the phone itself (in the case of failing modbusproxy)

-- INSERT INTO 'setup' VALUES('S200','D05162F460E2','','mac until discovery starts to work','droid1'); -- hvv kp26
-- INSERT INTO 'setup' VALUES('S200','D05162F460A9','','mac until discovery starts to work','droid1'); -- 58846849 KP6 jamas, sqlite db riknenud.
-- INSERT INTO 'setup' VALUES('S200','D05162F460E5','','mac until discovery starts to work','droid1'); -- hvv kp13 58845796
-- INSERT INTO 'setup' VALUES('S200','D05162F460BE','','mac until discovery starts to work','droid1'); -- KP24
-- INSERT INTO 'setup' VALUES('S200','D05162F4608A','','mac until discovery starts to work','droid1'); -- 58846671 sql, dichannels?? recreate ja uuesti saatmine ei aidanud
-- INSERT INTO 'setup' VALUES('S200','D05162F46300','','mac until discovery starts to work','droid1'); -- hvv kp11 58846671
-- INSERT INTO 'setup' VALUES('S200','D05162F46217','','mac until discovery starts to work','droid1'); -- kp4 58845916
-- INSERT INTO 'setup' VALUES('S200','D05162F45EB4','','mac until discovery starts to work','droid1'); -- kp19
-- INSERT INTO 'setup' VALUES('S200','D05162F4636F','','mac until discovery starts to work','droid1'); -- hullo kp2, 58846470
-- INSERT INTO 'setup' VALUES('S200','D05162F46093','','mac until discovery starts to work','droid1'); -- hvv kp5
-- INSERT INTO 'setup' VALUES('S200','D05162F460DB','','mac until discovery starts to work','droid1'); -- hvv kp15 58845870
-- INSERT INTO 'setup' VALUES('S200','D05162F46090','','mac until discovery starts to work','droid1'); -- hvv 17 58600168  0.19..0.41m
-- INSERT INTO 'setup' VALUES('S200','D05162F460D5','','mac until discovery starts to work','droid1'); -- kp5 53045753
-- INSERT INTO 'setup' VALUES('S200','D05162F462F8','','mac until discovery starts to work','droid1'); -- hvv kp20
-- INSERT INTO 'setup' VALUES('S200','D05162F46087','','mac until discovery starts to work','droid1'); -- hvv kp2 58846570
-- INSERT INTO 'setup' VALUES('S200','D05162F460B3','','mac until discovery starts to work','droid1'); -- 58845956
-- INSERT INTO 'setup' VALUES('S200','D05162F46081','','mac until discovery starts to work','droid1'); -- hvv kp23 58843856
-- INSERT INTO 'setup' VALUES('S200','D05162F462C2','','mac until discovery starts to work','droid1'); -- hvv kp25 58845925
-- INSERT INTO 'setup' VALUES('S200','D05162F46064','','mac until discovery starts to work','droid1'); -- 58556326 kp21 uusi
-- INSERT INTO 'setup' VALUES('S200','D05162F4608F','','mac until discovery starts to work','droid1'); -- 58846895 hvv kiltsi
-- INSERT INTO 'setup' VALUES('S200','D05162F45CE3','','mac until discovery starts to work','droid1'); -- 58845866 hvv pyrksi puhasti juures, keskmine
-- INSERT INTO 'setup' VALUES('S200','D05162F45FD0','','mac until discovery starts to work','droid1'); -- 58846934 kahtlane, lag, valikupunn vobeles, oli  kp26
-- INSERT INTO 'setup' VALUES('S200','D05162F46299','','mac until discovery starts to work','droid1'); -- 58843847 
-- INSERT INTO 'setup' VALUES('S200','D05162F45CE2','','mac until discovery starts to work','droid1'); -- 58553791 -- risti kp1 videviku
-- INSERT INTO 'setup' VALUES('S200','D05162F46301','','mac until discovery starts to work','droid1'); -- 56268654 vormsi kortsi kp3
-- INSERT INTO 'setup' VALUES('S200','D05162F460D8','','mac until discovery starts to work','droid1'); -- 58845986 


INSERT INTO 'setup' VALUES('S202','chk serial','','phone number','sim card'); -- phone number - change as needed
-- INSERT INTO 'setup' VALUES('S300','','','UUID','unique installation id');  -- from modbusproxy
INSERT INTO 'setup' VALUES('S400','http://www.itvilla.ee','','supporthost','for pull, push cmd');
INSERT INTO 'setup' VALUES('S401','upload.php','','requests.post','for push cmd');
INSERT INTO 'setup' VALUES('S402','Basic cHlhcHA6QkVMYXVwb2E=','','authorization header','for push cmd');
INSERT INTO 'setup' VALUES('S403','support/pyapp/$mac','','upload/dnload directory','for pull and push cmd'); --  $mac will be replaced by wlan mac

INSERT INTO 'setup' VALUES('S512','test','','location',''); 

INSERT INTO 'setup' VALUES('W1.271','192','','ANA mode','ai1..ai6, adi7..adi8'); -- adi7 ja adi8 pulldown
INSERT INTO 'setup' VALUES('W1.275','0','','ANA direction','kogu ANA on sis'); --  all inputs
INSERT INTO 'setup' VALUES('W1.276','10','','usbreset powerup protection','10 s lisaaega'); -- usbreset powerup protection
INSERT INTO 'setup' VALUES('W1.277','1300','','usbreset pulse','20 ja 5 s'); -- usbreset 30 s delay 5 s pulse 
INSERT INTO 'setup' VALUES('W1.278','10','','button powerup protection','10 s lisaaega'); -- buttonpulse powerprotection
INSERT INTO 'setup' VALUES('W1.279','1380','','button pulse','100 ja 5 s'); -- buttonpulse 120 s delay 5 s pulse 

-- R... values will only be reported during channelconfiguration()
INSERT INTO 'setup' VALUES('R1.256','','','dev type',''); -- read only
INSERT INTO 'setup' VALUES('R1.257','','','fw version',''); -- 

-- lisada supportserver ja mon server aadressid

CREATE UNIQUE INDEX reg_setup on 'setup'(register);
COMMIT;
