-- LINUX version, longer watchdog delay. NEW PIC!
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE setup(register,value,ts,desc,comment); -- desc jaab UI kaudu naha,  comment on enda jaoks. ts on muutmise aeg s, MIKS mitte mba, reg value? setup muutuja reg:value...

-- R... values will only be reported during channelconfiguration()
INSERT INTO 'setup' VALUES('R1.256','','','dev type',''); -- read only
INSERT INTO 'setup' VALUES('R1.257','','','fw version',''); -- start with this, W1.270,271,275 depend on this !

INSERT INTO 'setup' VALUES('S400','http://www.itvilla.ee','','supporthost','for pull, push cmd');
INSERT INTO 'setup' VALUES('S401','upload.php','','requests.post','for push cmd');
INSERT INTO 'setup' VALUES('S402','Basic cHlhcHA6QkVMYXVwb2E=','','authorization header','for push cmd');
INSERT INTO 'setup' VALUES('S403','support/pyapp/$mac','','upload/dnload directory','for pull and push cmd'); --  $mac will be replaced by wlan mac

INSERT INTO 'setup' VALUES('S512','test','','location','');
INSERT INTO 'setup' VALUES('S514','195.222.15.51','','syslog server ip address','local broadcast in use if empty or 0.0.0.0 or 255.255.255.255'); -- port is fixed to udp 514.

INSERT INTO 'setup' VALUES('W1.270','0','','Vref','ai1..ai6, adi7..adi8'); -- ref voltage 0000=5v, 4.096V jaoks 0030, 2.048V puhul 0020 (ONLY NEW PIC!)

-- INSERT INTO 'setup' VALUES('W1.271','192','','ANA mode ','ai1..ai6, adi7..adi8'); -- old pic (16f877), 2 oldest bits are di, the rest ai
INSERT INTO 'setup' VALUES('W1.271','0','','DI XOR 0000','inversioon'); -- NEW PIC. DI inversion bitmap. 0=hi active, 1=low active

INSERT INTO 'setup' VALUES('W1.272','49152','','powerup mode','do on startup 0xC000'); -- do7 ja do8 up (commLED ja pwr_gsm)

-- INSERT INTO 'setup' VALUES('W1.275','0','','ANA direction','kogu ANA on sis'); --  old pic, all inputs
INSERT INTO 'setup' VALUES('W1.275','49152','','ANA mode + direction c000','kogu ANA on sis'); --  NEW pic, ANA port+mode bitmap, LSB: 1=output, 0=input. MSB: AI/DI, 0=AI

INSERT INTO 'setup' VALUES('W1.276','10','','usbreset powerup protection','10 s lisaaega'); -- usbreset powerup protection
INSERT INTO 'setup' VALUES('W1.277','1380','','usbreset pulse','5 ja 100 s, 0x0564'); -- usbreset 5 s pulse 100 s delay (ft31x+usb5v) / et sobiks ka linuxile 
INSERT INTO 'setup' VALUES('W1.278','10','','button powerup protection','10 s lisaaega'); -- buttonpulse powerprotection
INSERT INTO 'setup' VALUES('W1.279','1380','','button pulse','100 ja 5 s'); -- buttonpulse 100 s delay 5 s pulse , useless for linux

-- lisada supportserver ja mon server aadressid

CREATE UNIQUE INDEX reg_setup on 'setup'(register);
COMMIT;
