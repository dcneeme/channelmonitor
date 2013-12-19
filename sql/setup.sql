-- android seadme setup tabel, baasi modbus_channels. systeem sama nagu barioneti muutujatega!
-- kindlasti vaja anda mon serverid, max teavitusintervall, obj nimetus jne

PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE setup(register,value,ts,desc,comment); -- desc jaab UI kaudu naha,  comment on enda jaoks. ts on muutmise aeg s, MIKS mitte mba, reg value? setup muutuja reg:value...

INSERT INTO 'setup' VALUES('S400','http://www.itvilla.ee','','supporthost','for pull, push cmd');
INSERT INTO 'setup' VALUES('S401','upload.php','','requests.post','for push cmd');
INSERT INTO 'setup' VALUES('S402','Basic cHlhcHA6QkVMYXVwb2E=','','authorization header','for push cmd');
INSERT INTO 'setup' VALUES('S403','support/pyapp/$mac','','upload/dnload directory','for pull and push cmd'); --  $mac will be replaced by wlan mac

INSERT INTO 'setup' VALUES('S512','test','','location',''); 

INSERT INTO 'setup' VALUES('W1.271','192','','ANA mode','ai1..ai6, adi7..adi8'); -- adi7 ja adi8 pulldown
INSERT INTO 'setup' VALUES('W1.272','49152','','powerup mode','do on startup 0xC000'); -- do7 ja do8 up (commLED ja pwr_gsm)
INSERT INTO 'setup' VALUES('W1.275','0','','ANA direction','kogu ANA on sis'); --  all inputs
INSERT INTO 'setup' VALUES('W1.276','10','','usbreset powerup protection','10 s lisaaega'); -- usbreset powerup protection
INSERT INTO 'setup' VALUES('W1.277','1340','','usbreset pulse','5 ja 60 s, 0x053c'); -- usbreset 5 s pulse 60 s delay / et sobiks ka linuxile 
INSERT INTO 'setup' VALUES('W1.278','10','','button powerup protection','10 s lisaaega'); -- buttonpulse powerprotection
INSERT INTO 'setup' VALUES('W1.279','1380','','button pulse','100 ja 5 s'); -- buttonpulse 120 s delay 5 s pulse 

-- R... values will only be reported during channelconfiguration()
INSERT INTO 'setup' VALUES('R1.256','','','dev type',''); -- read only
INSERT INTO 'setup' VALUES('R1.257','','','fw version',''); -- 

-- lisada supportserver ja mon server aadressid

CREATE UNIQUE INDEX reg_setup on 'setup'(register);
COMMIT;
