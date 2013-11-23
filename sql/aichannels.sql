-- DC5888-2 systemtest pumplad  hvv jaoks variant 1
-- ai1..ai4 on analoog, 4..20mA. rohk, nivoo, p1 vool, p2 vool.  ai7=3,3v, ai8=temperatuur.

-- analogue values and temperatures channel definitions for android-based automation controller 
-- x1 ja x2 for input range, y1 y2 for output range. conversion based on 2 points x1,y1 and y1,y2. x=raw, y=value.
-- avg defines averaging strength, has effect starting from 2

-- # CONFIGURATION BITS
-- # siin ei ole tegemist ind ja grp teenuste eristamisega, ind teenused konfitakse samadel alustel eraldi!
-- # konfime poolbaidi vaartustega, siis hex kujul hea vaadata. vanem hi, noorem lo!
-- # x0 - alla outlo ikka ok, 0x - yle outhi ikka ok 
-- # x1 - alla outlo warning, 1x - yle outhi warning
-- # x2 - alla outlo critical, 2x - yle outhi critical
-- # x3 - alla outlo ei saada, 3x - yle outhi ei saada
-- # lisaks bit 2 lisamine asendab vaartuse nulliga / kas on vaja?
-- # lisaks bit 4 teeb veel midagi / reserv

-- x1 x2 y1 y2 values needed also for virtual setup values, where no linear conversions is needed. use 0 100 0 100 not to convert

PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
-- drop table aichannels; -- remove the old one

CREATE TABLE aichannels(mba,regadd,val_reg,member,cfg,x1,x2,y1,y2,outlo,outhi,avg,block,raw,value,status,ts,desc,comment,type integer); 
-- type is for category flagging, 0=do, 1 = di, 2=ai, 3=ti. use only 2 and 3 in this table (4=humidity, 5=co2?)

-- INSERT INTO "aichannels" VALUES('1','600','T1W','1','17','0','80','0','50','0','500','1','','','110','0','','temp channel 1','286EE441',3); -- ds18b20 sensor
-- INSERT INTO "aichannels" VALUES('','','T1W','2','0','0','100','0','100','0','','1','','0','50','0','','temp channel 1','lo limit',3); -- just a line on the graph
-- INSERT INTO "aichannels" VALUES('','','T1W','3','0','0','100','0','100','0','','1','','500','500','0','','temp channel 1','hi limit',3); -- just a line on the graph

INSERT INTO "aichannels" VALUES('1','2','PVW','1','17','205','1023','0','1000','0','1000','1','','','110','0','','pressure','ai1',2); -- 4..20mA sensor, voltage 1..5V
INSERT INTO "aichannels" VALUES('','','PVW','2','0','0','100','0','100','0','','1','','0','0','0','','ai1','pressure lo limit',2); -- just a line on the graph
INSERT INTO "aichannels" VALUES('','','PVW','3','0','0','100','0','100','0','','1','','500','1000','0','','ai1','pressure hi limit',2); -- just a line on the graph

-- INSERT INTO "aichannels" VALUES('1','3','LVW','1','17','102','1023','0','3000','100','1000','1','','','110','0','','water level','ai2',2); -- 4..20mA sensor, voltage 1..5V
-- INSERT INTO "aichannels" VALUES('1','3','LVW','1','17','205','1023','0','3000','100','1000','1','','','110','0','','water level','ai2',2); -- 4..20mA sensor, voltage 1..5V
INSERT INTO "aichannels" VALUES('1','3','LVW','1','17','205','1023','0','5000','100','1000','1','','','110','0','','water level','ai2',2); -- pyrksi kp3

INSERT INTO "aichannels" VALUES('','','LVW','2','0','0','100','0','100','0','','1','','0','100','0','','level lo warning','lo limit',2); -- just a line on the graph
INSERT INTO "aichannels" VALUES('','','LVW','3','0','0','100','0','100','0','','1','','0','1000','0','','level hi warning','hi limit',2); -- just a line on the graph

-- INSERT INTO "aichannels" VALUES('1','4','I1W','1','17','102','1023','0','50000','1000','10000','2','','','110','0','','pump1 current mA','ai3',2); -- kp15 125 ohm
-- INSERT INTO "aichannels" VALUES('1','5','I1W','2','17','102','1023','0','50000','1000','10000','2','','','110','0','','pump1 current mA','ai4',2); -- kp15 125 ohm
INSERT INTO "aichannels" VALUES('1','4','I1W','1','17','410','1023','0','20000','1000','10000','2','','','110','0','','pump1 current mA','ai3',2); -- 4..20mA sensor, voltage 1..5V
INSERT INTO "aichannels" VALUES('1','5','I1W','2','17','410','1023','0','20000','1000','10000','2','','','110','0','','pump1 current mA','ai4',2); -- 4..20mA sensor, voltage 1..5V
-- INSERT INTO "aichannels" VALUES('1','4','I1W','1','17','205','1023','0','25000','1000','10000','2','','','110','0','','pump1 current mA','ai3',2); -- 4..20mA sensor, voltage 1..5V
-- INSERT INTO "aichannels" VALUES('1','5','I1W','2','17','205','1023','0','25000','1000','10000','2','','','110','0','','pump1 current mA','ai4',2); -- 4..20mA sensor, voltage 1..5V
INSERT INTO "aichannels" VALUES('','','I1W','3','0','0','100','0','100','0','','1','','0','1000','0','','current lo warning','lo limit',2); -- just a line on the graph
INSERT INTO "aichannels" VALUES('','','I1W','4','0','0','100','0','100','0','','1','','0','10000','0','','current hi warning','hi limit',2); -- just a line on the graph

-- INSERT INTO "aichannels" VALUES('1','3','33V','1','0','0','1023','0','5000','50','500','1','','','3300','0','','3V3 chk ai5','akutoite pingekontroll',3); -- 3.3V chk

INSERT INTO "aichannels" VALUES('1','7','T1W','1','17','143','358','200','1250','50','500','3','','','110','0','','temp channel 2','ai7 voltage',3); -- tc1047 sensor
INSERT INTO "aichannels" VALUES('','','T1W','2','0','0','100','0','100','0','','1','','0','50','0','','temp channel 1','lo limit',3); -- just a line on the graph
INSERT INTO "aichannels" VALUES('','','T1W','3','0','0','100','0','100','0','','1','','0','500','0','','temp channel 1','hi limit',3); -- just a line on the graph


-- lisa siia torustiku rohk reg 2 ja pumpade voolud reg 4 ning 5

CREATE UNIQUE INDEX ai_regmember on 'aichannels'(val_reg,member); -- every service member only once
COMMIT;
