-- devices attached to the modbusRTU or modbusTCP network
BEGIN TRANSACTION; 
-- count0..count3 are channel counts for do, do, ai an 1wire.

CREATE TABLE 'devices'(num integer,rtuaddr integer,tcpaddr,status integer,name,location,descr,count0 integer,count1 integer,count2 integer,count3 integer); -- ebables using mixed rtu and tcp inputs
-- what are count0...count3, channel types?

INSERT INTO 'devices' VALUES(1,1,'127.0.0.1:10502',0,'DC5888-2','1st floor','droid4control kontroller',8,8,8,8); -- the same as for barionet, fixed addresses for system devices
INSERT INTO 'devices' VALUES(2,255,'127.0.0.1:10502',0,'ModbusProxy','','droid4control controller phone',8,8,8,8); -

-- INSERT INTO 'devices' VALUES(2,2,'127.0.0.1:10502',0,'Barix IO12','1st floor','laiendusmoodul rs485'); -- the same as for barionet
-- INSERT INTO 'devices' VALUES(3,0,'10.0.0.11:502',0,'Barionet100','2nd floor','kytte kontroller'); -- the same as for barionet

-- di can be counter. ai can be di or do. subtype? only do (type=0) has subtype 0...
-- possible type.subtype combinations are 
-- 0.0,  1.1, 1.4,  2.0, 2.1, 2.2,  3.3
 
CREATE UNIQUE INDEX num_devices on 'devices'(num); -- device ordering numbers must be unique
CREATE UNIQUE INDEX addr_devices on 'devices'(rtuaddr,tcpaddr); -- device addresses must be unique

COMMIT;
    