-- DC58888-2 systemtesti pumplad variant 1 hvv jaoks. haapsalu hvvmon2

-- modbus di and do channels for android based automation controller with possible extension modules
-- if output channels should ne reported to monitoring, they must be defined here in addition to dochannels
-- member 1..n defines multivalue service content. mixed input and output channels in one service are also possible!
-- status and dsc are last known results, see timestamp ts as well when using
-- also power counting may be involved, see cfg 

-- CONF BITS
-- # 1 - value 1 = warningu (values can be 0 or 1 only)
-- # 2 - value 1 = critical, 
-- # 4 - value inversion 
-- # 8 - value to status inversion
-- # 16 - immediate notification on value change (whole multivcalue service will be (re)reported)
-- # 32 - this channel is actually a writable coil output, not a bit from the register (takes value 0000 or FF00 as value to be written, function code 05 instead of 06!)
--     when reading coil, the output will be in the lowest bit, so 0 is correct as bit value

-- # block sending. 1 = read, but no notifications to server. 2=do not even read, temporarely register down or something...

PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;

CREATE TABLE dichannels(mba,regadd,bit,val_reg,member,cfg,block,value,status,ts_chg,chg,desc,comment,ts_msg,type integer); -- ts_chg is update toime (happens on change only), ts_msg =notif
-- value is bit value 0 or 1, to become a member value with or without inversion
-- status values can be 0..3, depending on cfg. member values to service value via OR (bigger value wins)
-- if newvalue is different from value, write will happen. do not enter newvalues for read only register related rows.
-- type is for category flagging, 0=do, 1 = di, 2=ai, 3=ti. use only 0 and 1 in this table

--AI as di channels (1..4 are ai)
INSERT INTO "dichannels" VALUES('1','1','6','R1W','1','21','0','0','1','0','','','ai7 as di','R1W',1); -- pingega p1 on, adi7. w.
INSERT INTO "dichannels" VALUES('1','1','7','R1W','2','21','0','0','1','0','','','ai8 as di','R1W',1); -- p1 on, adi8

--di channels 1..8
INSERT INTO "dichannels" VALUES('1','1','8','F1W','1','21','0','0','1','0','','','mba1 DI1','f1w.1',1); -- p1 ok, di1
INSERT INTO "dichannels" VALUES('1','1','9','F1W','2','21','0','0','0','0','','','mba1 DI2','f1w.2',1); -- p2 ok, di2
INSERT INTO "dichannels" VALUES('1','1','10','APS','1','21','0','0','1','1','','','mba1 DI3','aps',1); -- pingepiirik, di3
INSERT INTO "dichannels" VALUES('1','1','11','PWS','1','18','0','0','1','0','','','di4 as 230V chk','PWS',1); -- 230V norm pingega. cfg 18 ja 30 moju on sama! 
INSERT INTO "dichannels" VALUES('1','1','12','LHS','1','26','0','0','1','0','','','ai8 as di','LHS',1); -- uputus, adi8
INSERT INTO "dichannels" VALUES('1','1','13','BRS','1','18','0','0','1','0','','','mba1 DI6','BRS',1); -- uks, di6. w voltage=ok. 18 on oige!

-- INSERT INTO "dichannels" VALUES('1','1','14','D1W','7','0','0','0','1','0','','','mba1 DI7','',1); -- en mootja, vt counters
-- INSERT INTO "dichannels" VALUES('1','1','15','D1W','8','0','0','0','1','1','','','mba1 DI8','',1); 

CREATE UNIQUE INDEX di_regmember on 'dichannels'(val_reg,member);
-- NB bits and registers are not necessarily unique!

COMMIT;
