#!/usr/bin/python
# this script is 1) constantly updating the channel tables according to the modbus register content; 2) sending messages to the central server; 
# 3) listening commands and new setup values from the central server; 4) comparing the dochannel values with actual do values in dichannels table and writes to eliminate  the diff.
# currently supported commands: REBOOT, VARLIST, pull, sqlread, run
 
APVER='channelmonitor3.py 23.06.2013'  # give parameters if not running on android
# testimiseks linuxi peal: ./channelmonitor3.py 10.0.0.100:10502 pumpla_bn, kus 10.0.0.100 on ioplaadiga yhendatud mobla wlan ip ja pumpla_bn on sql kataloog
# voimalik on paralleeltoo nii androidi kui linuxi peal, monitooringusse raporteerivad eraldi mac pealt (nii nagu setup failis S202 kirjas ..


# 23.06.2013 git kasutus, tykeldamine imporditavateks juppideks: channelmonitor, pymodbus, read_dichannel_bits(), make_dichannel_svc(), write_dochannels(), 
#   read_aichannels(), make_aichannels(), read_counters(), udp_send(). algne fail channelmonitor3.py jaagu vordluseks alles.

 
# PROBLEMS and TODO
# inserting to sent2server has problems. skipping it for now, no local log therefore.
# separate ai reading and ai sending intervals!
# send gsm signal level to monitoring!
# add sqlite tables test, start dbREcreate together with channelmonitor stopping if it feels necessary to restore normal operation! 

#modbusproxy registers / Only one register can be read  or write at time (registers are sometimes long)
#000-099 ModbusProxy information
        #0:x - ModbuProxy long version string <app version>.<commit seq>-<branch>-<short sha1>
#100-199 ModbusProxy configuration
        #100:x - SL4A USB connected autostart script name
        #101:x - SL4A ModbusProxy service autostart script name
#200-299 ModbusProxy log and counters
        #200:1 - USB status
#300-399 Phone information
        #300:8 - UUID
        #301:x - device ID
        #302:x - SIM serial number
        #303:x - line1number (phone number if stored on SIM)
        #304:1 - cell RSSI - returns 0 on sony xperia!!!
        #305:1 - WiFi RSSI     / returns ffc0 if very close to ap
        #310:3 - wlan0 MAC address     / ok, ex
        #313:2 - wlan0 IPv4 address  
        
        

# ### procedures ######################
    
    
def subexec(exec_cmd,submode): # returns output of a subprocess, like a shell script or command
    #proc=subprocess.Popen([exec_cmd], shell=True, stdout=DEVNULL, stderr=DEVNULL)
    if submode == 0: # return exit status, 0 or more
        proc=subprocess.Popen([exec_cmd], shell=True, stdout=DEVNULL, stderr=DEVNULL)
        proc.wait()
        return proc.returncode  # return just the subprocess exit code
    else: # return everything from sdout
        proc=subprocess.Popen([exec_cmd], shell=True, stdout=subprocess.PIPE)
        result = proc.communicate()[0]
        #proc.wait()
        return result
    
    
    
def sqlread(table): # drops the existing table in parameter and reads from file table.sql that must exist / to restore
    global conn1tables, conn3tables,conn4tables
    Cmd='drop table if exists '+table
    filename=table+'.sql' # the file to read from
    try:
        sql = open(filename).read()
    except:
        msg='sqlreload: could not read into table file '+filename
        print(msg)
        log2file(msg)
        traceback.print_exc()
        time.sleep(1)
        return 1
        
    try:
        if table in conn1tables:
            conn1.execute(Cmd) # drop the table if it exists
            conn1.executescript(sql) # read table into database
        if table in conn3tables:
            conn3.execute(Cmd)
            conn3.executescript(sql) # read table into database
        if table in conn4tables:
            conn4.execute(Cmd)
            conn4.executescript(sql) # read table into database
        msg='sqlreload: dropped+read the table '+table
        log2file(msg)
        return 0
    except:
        traceback.print_exc()
        msg='sqlreload: COULD NOT drop table '+table
        print(msg)
        log2file(msg)
        time.sleep(1)
        return 1
            
        
        
    
def channelconfig(): # channel setup register setting based on devicetype and channel registers configuration. try to check channel conflicts
    global tcperr,inumm,ts,sendstring #,MBsta # not yet used, add handling
    mba=0
    register=''
    value=0
    regok=0
    mba_array=[]
    respcode=read_register(1,1,1) # test connection with proxy, based on di register read success (use for dc5888-2)
    #MBsta[0]=respcode
    if respcode<>0:
        print "no modbusproxy connection (1,1,1)!"
        sys.stdout.flush()
        time.sleep(1)
        return 2
    else: # proxy conn ok, SET AND CHECK channel configurations from setup registers W<mba>.<regadd>
        print "modbusproxy connection (1,1,1) ok!"
        #find devices and their B W S setup variables from setup
        #Cmd3="select rtuaddr from devices order by rtuaddr"
        #cursor3.execute(Cmd3) # read used mba addresses into cursor
        #conn3.commit()
        #for row in cursor3:
        #    mba_array.append(row[0]) # useful for webUI?
        
        Cmd4="select register,value from setup" 
        cursor4.execute(Cmd4) # read setup variables into cursor
        conn4.commit()
        for row in cursor4:
            regok=0
            msg='setup record '+repr(row)
            print(msg)
            log2file(msg)
            register=row[0] # contains W<mba>.<regadd> or R<mba>.<regadd>
            if '.' in register: # dot is needed
                try:
                    mba=int(register[1:].split('.')[0])
                    regadd=int(register[1:].split('.')[1])
                    msg='going to set or read register '+register+' at mba '+str(mba)+', regadd '+str(regadd)
                    regok=1
                except:
                    msg='invalid mba and/or register data for '+register
                print(msg)
                log2file(msg)
                
                if regok == 1:
                    if row[1] <>'': # value to WRITE  must not be empty
                        value=int(row[1]) # contains 16 bit word
                        msg='sending config wordh '+format("%04x" % value)+' to mba '+str(mba)+' regadd '+str(regadd)
                        time.sleep(0.1) # successive sending without delay may cause failures!
                        respcode=write_register(mba,regadd,value,0) # write_register sets MBsta[] as well
                        #MBsta[mba-1]=respcode
                        if respcode<>0:
                            msg=msg+' - write_register() PROBLEM!'
                            print(msg)
                            log2file(msg)
                            sys.stdout.flush()
                            time.sleep(1)
                            #return 1 # continue with others!
                        
                        time.sleep(0.1) # delay needed after write before read!
                        
                    if read_register(mba,regadd,1) == 0: # read back, can also happen without writing first!
                        if register[0] == 'W': # writable
                            if tcpdata == value: # the actual value verified
                                msg=msg+' - written and read, verified OK'
                                print(msg)
                                log2file(msg)
                            else:
                                msg=' - unexpected value '+str(tcpdata)+' during verification, register '+str(mba)+'.'+str(regadd)
                                print(msg)
                                log2file(msg)
                                sys.stdout.flush()
                                time.sleep(0.5)
                                return 1
                        else: # readable only
                            msg='reading configuration data from mba.reg '+str(mba)+'.'+str(regadd)
                        #send the actual data to the monitoring server
                        sendstring=sendstring+"R"+str(mba)+"."+str(regadd)+":"+str(tcpdata)+"\n"  # register content reported as decimal
                        
                    else:
                        msg=' - could not read back the register mba.reg '+str(mba)+'.'+str(regadd)
                        print(msg)
                        log2file(msg)
                        sys.stdout.flush()
                        time.sleep(1)
                        return 1

        udpsend(inumm,int(ts)) # sending to the monitoring server
        
    sys.stdout.flush()
    time.sleep(0.5)
    return 0
        
        


def modbus_comm(sdata): # send and receive to/from modbus devices
    global tcpaddr, tcpport, response, tcpmode #,MBsta
    
    loccount=1 # by default 1 register to read
    locmba=ord(sdata[tcpmode*6]) # modbus address
    locfunction=ord(sdata[1+tcpmode*6]) # command to use
    locreg=256*ord(sdata[2+tcpmode*6])+ord(sdata[3+tcpmode*6])
    retexception=0
    ExpExc=3+tcpmode*6 # possible exception length
    
    if tcpmode>1:
        tcpmode=1 # never higher.
        
    if locfunction == 3: # read register(s)
        loccount=ord(sdata[5+tcpmode*6])  # using only LSB of register count, we never read more than 255 register in one request!
        ExpLen=3+abs(loccount)*2+6*tcpmode # length of expected response
  
        #print 'modbus_comm:',loccount,'register(s) to read, tcpmode',tcpmode # debug
        
    
    try: 
        tcpsocket.sendall(sdata)
        #print "==>",tcpaddr,tcpport,sdata.encode('hex') # debug
        ready=select.select([tcpsocket],[],[],tcpwait) # timeout to wait for answer. 
        
    except:
        #print 'failed sending read request to',tcpaddr, tcpport # need to restart the socket
        print 'x',
        #traceback.print_exc()
        return 4 # restart socket
     

    if ready[0]: # midagi on tulnud
        response = tcpsocket.recv(1024) # kuulame
        msg="<== "+tcpaddr+":"+str(tcpport)+" "+response.encode('hex')
        #print msg  # debug
        if len(response) == ExpExc: # likely exception 
            retfunction=ord(response[1+tcpmode*6])
            #if retfunction <> locfunction: # the same as sent
            if (retfunction&128): # error bit raised in response function code
                retexception=ord(response[2+tcpmode*6])
                #print 'modbus_comm() locfunction, retfunction,retexception',format("%02x" % locfunction), format("%02x" % retfunction), format("%02x" % retexception) #debug
                #print 'exception source is the device with mba',locmba,'illegal command or address'
                    
                if retexception == 10: # 0A hex, gw problem
                    msg='modbusERR10: gw - RS485 unreachable'
                    print(msg)
                    log2file(msg)
                    time.sleep(1)
                    return 3 # gw problem

                if retexception == 11: # 0B hex, device unreachable
                    msg='modbusERR11: no response from mba'+str(locmba)
                    print(msg)
                    log2file(msg)
                    time.sleep(1)
                    return 2 # device problem
                
                if retexception == 4: # 04 hex, device failure, could be crc error
                    msg='modbusERR4: crc error from mba'+str(locmba)
                    print(msg)
                    log2file(msg) # ajutine?
                    time.sleep(1)
                    return 1 # crc problem

                    
        if locfunction == 3: # register(s) read
            if len(response) <> ExpLen: # not a valid response, while for barionet reg count can be negative!
                # counter read response example: 15010000000700030477c80001
                print 'modbusERR: mba '+str(locmba)+' reg '+str(locreg)+' read failure - illegal response length of',len(response),'instead of',3+abs(loccount)*2+tcpmode*6,response.encode('hex')
                return 1 # back to parent
        else: # register write
            if sdata <> response[:len(sdata)]: # response is different from expected
                print 'modbusERR: mba '+str(locmba)+' reg '+str(locreg)+' write failure - illegal response content or length'
                return 1 # back to parent
                
    else: # no data from modbusproxy
        msg='modbusERR: no answer in 2s on request from '+tcpaddr+':'+str(tcpport) # debug
        print(msg)
        log2file(msg)
        time.sleep(2)
        return 4 # bigger problem, modbusproxy MUST response. no conn?
    
    #time.sleep(0.05) # to prevent sending immediate next request
    return 0



def read_register(locmba,locreg,loccount): # read via modbustcp, params mba,register address to start from,register count.
    # the result will be in global variable tcpdata, while data from multiple registers will be joined into one value, 32 bits or more
    #local locmba,locreg,loccount
    global tcpport, tcpaddr, tcpdata, tcpmode, tcpwait,MBsta  # tcpmode 0 or 1, controls header presence to the proxy and the expected response length
    hexstring=""
    mbah=format("%02x" % locmba) # mbah=mba.encode('hex') # hex kujul mba
    regaddrh=format("%04x" % locreg) # regaddr=reg.encode('hex') # hex kujul reg addr (reg nr on see+1!)
    regcounth=format("%04x" % abs(loccount)) # reg arv hex, abs vaartus sest negatiivne ei tohi olla!
    
    if tcpmode == 1: # add header
        hexstring="150100000006"
    
    hexstring=hexstring+mbah+"03"+regaddrh+regcounth
    
    if len(hexstring)%2<>0: # odd length??
        print 'modbus send canceled due to odd length of hexstring',hexstring
        sys.stdout.flush()
        time.sleep(1)
        return 1
    
    sdata=hexstring.decode('hex') #binary string, not hex
    
    tcpdata=0 # vastus esialgu 0
    tcpessa=0 # esialgu, local
    
    respcode=modbus_comm(sdata) # returns binary string from modbus   ################################## modbus communication to read ################################
    MBsta[locmba-1]=respcode
    
    if respcode == 0: # got valid answer
        tcpdat=response[9:] # cut off the start to get result as binary string
        lenn=len(tcpdat) # data length
        if lenn%2==0: # even
            for num in range(len(tcpdat)): # put bytes together into word
                if num%2 == 0: #algas jargmine sona loendist tulevas infos 
                    tcpessa=tcpdata # meelde sona,  mis praeguseks olemas (enne saadeti)
                    tcpdata=0 # next byte starts from zero
                
                tcpdata=256*tcpdata+ord(tcpdat[num]) # word from bytes
                #tcpdata=(tcpdata<<4)+ord(tcpdat[num]) # there was some problem with this way to do the same. ehk peaks 8 bitti nihutama ikka??
                
            #if loccount == 1 and tcpdata >= 32768: # <0: # must be negative temperature reading as 10 bit adc cannot give such a result
            #    tcpdata=tcpdata-65536  # positiivseks jalle, negatiivsete vaartustega siin ei tegelda. adc tulemus on pos skaalas. peab mojuma ka temperatuuridele!
            #    print 'reg',locreg,'temperature converted from negative raw ',tcpessa,'to tcpdata',tcpdata # 'read_register() added 65536 to tcpdata, got',tcpdata
                    
            if loccount == -2: # barionet loendi kus reg adrr kasvav jrk annab LSW MSW 
                if lenn == 4:  # 2 baidine vastus ehk 32 bitti
                    tcpdata=65536*tcpdata+tcpessa # 4-baidiseks vaartuseks, margita
                    #tcpdata=(tcpdata<<16)|tcpessa # 4-baidiseks vaartuseks, margita   
                    #print 'bn counter',locreg,' first came LSW',tcpessa,'hex',format("%04x" % tcpessa),', total',tcpdata,'hex',format("%08x" % tcpdata)  # ajutine                   
                    
            if loccount == 2: # normaalne loendi kus registrite jarjekorras MSW LSW
                if lenn == 4:  # 2 baidine vastus ehk 32 bitti
                    tcpdata=tcpdata+656636*tcpessa # 4-baidiseks vaartuseks, margita
                    #tcpdata=tcpdata|(tcpessa<<16) # 4-baidiseks vaartuseks, margita
                    #print 'normal counter',locreg,'first came MSW',tcpessa,'hex',format("%04x" % tcpessa),', total',tcpdata,'hex',format("%08x" % tcpdata) # ajutine                   
                    
            
        else:
            print 'invalid response length',lenn,'for result' 
            return 1
            
    else: # respcode not 0
        return respcode
    
    if MBsta <> [0, 0, 0, 0]: # debug
        print 'MBsta at read_register end',MBsta   # debug       
    return 0
# end read_register()


    
def write_register(mba,reg,wdata,coilmode): # writing one coil (mode=1) or 16-bit register (mode=0), 
    global tcpport, tcpaddr, tcpwait, tcpmode, lastreg, MBsta 
    mbah=format("%02x" % mba) # mbah=mba.encode('hex') # hex kujul mba
    regaddrh=format("%04x" % reg) # regaddr=reg.encode('hex') # hex kujul reg addr (reg nr on see+1!)
    if wdata>65535:
        print 'write_register(): too large value to fit into 16 bits:',wdata
        return 1
        
    if (coilmode&1) and wdata == 1: # write coil value FF00 instead of register
        wdata=65280 # hex FF00 instead of 1
        
    wdatah=format("%04x" % wdata) # data hex
    lastreg=reg # to remember last 
    response=''
    hexstring='' # string to send
    
    if tcpmode == 1: # tcp mode 
        hexstring="150100000006"
        
    if coilmode == 1: # this is coil not register, use command 05 instead of 06!
        hexstring=hexstring+mbah+"05"+regaddrh+wdatah # "0001" # kirjuta (alati 1 reg, arvu siin ei naidata)  
    else: # register
        hexstring=hexstring+mbah+"06"+regaddrh+wdatah # "0001" # kirjuta (alati 1 reg, arvu siin ei naidata)  
    
    if len(hexstring)%2<>0: # odd length??
        print 'write canceled due to odd length of hexstring',hexstring
        sys.stdout.flush()
        time.sleep(1)
        return 1
        
        
    sdata=hexstring.decode('hex') #binaarseks stringiks, mitte hex
    numm=0 # tulemus numbrina # hiljem selle asemel array

    respcode=modbus_comm(sdata) # returns binary string in tcpdata from modbus   ########## modbus communication to write #######
    MBsta[mba-1]=respcode
    if respcode == 0: # success
        msg='successfully wrote '+wdatah+' into register '+str(mba)+'.'+str(reg)
    else:
        msg='failed write of '+wdatah+' into register '+str(mba)+'.'+str(reg)
    print(msg)
    log2file(msg)
    sys.stdout.flush()
    return respcode
    
    # WRITE_REGISTER() END



def write_dochannels():
    # find out which do channels need to be changed based on dichannels and dochannels value differencies
    # and use write_register() write modbus registers (not coils) to get the desired result (all do channels must be also defined as di channels in dichannels table!)
    global inumm,ts,ts_inumm,mac,tcpdata,tcperr #,MBsta
    mba=0 # lokaalne siin
    omba=0 # previous value
    val_reg=''
    desc=''
    value=0
    word=0 # 16 bit register value
    #comment=''
    mcount=0
    #Cmd1='' 
    #Cmd3=''
    #Cmd4=''
    ts_created=ts # selle loeme teenuse ajamargiks
    
    try:
        Cmd3="BEGIN IMMEDIATE TRANSACTION" # conn3, kogu selle teenustegrupiga (aichannels) tegelemine on transaction - read only, no need...
        conn3.execute(Cmd3)
        
        # 0      1   2    3        4      5    6      7
        #mba,regadd,bit,bootvalue,value,rule,desc,comment
        
        # write coils first
        Cmd3="select dochannels.mba,dochannels.regadd,dochannels.value from dochannels left join dichannels on dochannels.mba = dichannels.mba AND dochannels.regadd = dichannels.regadd AND dochannels.bit = dichannels.bit where dochannels.value <> dichannels.value and (dichannels.cfg & 32) group by dochannels.mba,dochannels.regadd " 
        # the command above retrieves mba, regadd and value for coils
        #print "Cmd3=",Cmd3
        cursor3.execute(Cmd3)
        
        for row in cursor3: # got mba, regadd and value for coils that need to be updated / written
            regadd=0
            mba=0

            if row[0]<>'':
                mba=int(row[0]) # must be anumber
            if row[1]<>'':
                regadd=int(row[1]) # must be a number
            if row[1]<>'':
                value=int(row[2]) # 0 or 1 to be written
            print 'going to write as a coil register mba,regadd,value',mba,regadd,value # temporary
            
        
            respcode=write_register(mba,regadd,value,1+2*tcpmode)
            MBsta[locmba-1]=respcode
            if respcode == 0: # success
                tcperr=0
                
            else:
                tcperr=tcperr+1 # increase error count
                if respcode ==2:
                    print 'problem with coil',mba,regadd,value,'writing!'
                
        #conn3.commit()  # dicannel-bits transaction end

    except:
        print 'problem with dochannel grp select!'
        sys.stdout.flush()
        
    # end coil writing

    
    # write registers now. take values from dichannels and replace the bits found in dochannels. missing bits are zeroes.
    Cmd3="select dochannels.mba,dochannels.regadd,dochannels.value,dochannels.bit from dochannels left join dichannels on dochannels.mba = dichannels.mba AND dochannels.regadd = dichannels.regadd AND dochannels.bit = dichannels.bit where dochannels.value <> dichannels.value and not(dichannels.cfg & 32) group by dochannels.mba,dochannels.regadd,dochannels.bit" 
    # the command above retrieves mba, regadd that need to be written as 16 bit register
    #print "Cmd3=",Cmd3
    try:
        cursor3.execute(Cmd3)
        conn3.commit()
        
        for row in cursor3: # got mba, regadd and value for coils that need to be updated / written
            regadd=0
            mba=0
            bit=0
            value=0

            if row[0]<>'':
                mba=int(row[0]) # must be anumber
            if row[1]<>'':
                regadd=int(row[1]) # must be a number
            if row[2]<>'':
                value=int(row[2]) # 0 or 1 to be written
            if row[3]<>'':
                bit=int(row[3]) # bit, always 0 for coil, 0..15 for registers
                
            word=word+2**bit*value # adding bit values up to hget a word from bits 0..15. omitted bit values are 0 in the rsulting word!
                
            if mba <> omba and omba<>0: # next mba, write register using omba now
                print 'going to write a register mba,regadd,value',omba,regadd,word # temporary
            
                respcode=write_register(mba,regadd,word,2*tcpmode) 
                if respcode == 0: # ok
                    tcperr=0
                        
                else:
                    tcperr=tcperr+1
                    print 'problem with register',mba,regadd,value,'writing!'
                    #if respcode == 2: # register writing, gets converted to ff00 if value =1
                    #    socket_restart() # close and open tcpsocket
                        
            
        #conn3.commit()  # dicannel-bits transaction end

    except:
        print 'problem with dichannel grp select in write_do_channels!'
        sys.stdout.flush()
        #time.sleep(1)
        #traceback.print_exc()
    
    
    conn3.commit() # transaction end
    
    # write_dochannels() end. FRESHENED DICHANNELS TABLE VALUES AND CGH BITS (0 TO SEND, 1 TO PROCESS)



    


        
        
    

def read_dichannel_bits(): # binary inputs, changes to be found
# reads 16 bits as di or do channels to be reported to monitoring
# NB the same bits can be of different rows, to be reported in different services. services and their members must be unique
    locstring="" # see on siin lokaalne!
    global inumm,ts,ts_inumm,mac,tcpdata, tcperr,odiword
    mba=0 # lokaalne siin
    val_reg=''
    desc=''
    comment=''
    mcount=0
    #Cmd1='' 
    #Cmd3=''
    #Cmd4=''
    ts_created=ts # selle loeme teenuse ajamargiks
    ichg=0 # change mask iga mba kohta eraldi koostatav
    
    try:
        Cmd3="BEGIN IMMEDIATE TRANSACTION" # conn3
        conn3.execute(Cmd3) # 
        
        Cmd3="select mba,regadd from dichannels group by mba,regadd" # saame registrid mida lugeda vaja, mba ja regadd
        cursor3.execute(Cmd3)
        
        for row in cursor3: # teenuse seest teenuse liikmete formeerimise info lugemine, tuleb mitu rida
            regadd=0
            mba=0

            if row[0]<>'':
                mba=int(row[0]) # must ne number
            if row[1]<>'':
                regadd=int(row[1]) # must be number
            #mcount=int(row[1])
            if val_reg <> val_reg[:-1]+"S": #  only if val_reg does not end with S!
                sta_reg=val_reg[:-1]+"S" 
            else:
                sta_reg='' # no status added to the datagram 
                
            svc_name='' # unused?
            #print 'reading dichannel register mba,regadd',mba,regadd, # temporary
            
            Cmd3="select bit,value from dichannels where mba='"+str(mba)+"' and regadd='"+str(regadd)+"' group by regadd,bit" # loeme koik di kasutusel bitid sellelt registrilt
            cursor3a.execute(Cmd3)
            
            respcode=read_register(mba,regadd,1) # 1 register at the time
            #MBsta[mba-1]=respcode
            if respcode == 0: # successful DI register reading - continuous to catch changes! ################################
                tcperr=0
                #if odiword == -1: # first time here after restart
                #    odiword=tcpdata
                #if odiword<>tcpdata: # change
                #    ichg=(odiword^tcpdata)
                #    msg='DI word '+str(mba)+'.'+str(regadd)+' change, '+format("%04x" % odiword)+' -> '+format("%04x" % tcpdata)+', ichg '+format("%04x" % ichg)
                #    print(msg)
                #    log2file(msg)
                #    odiword=tcpdata
                #print 'got di word',format("%04x" % tcpdata) # tcpdata.encode('hex') # hex kujul 16 bitti, debug
                
                for srow in cursor3a: # for every mba list the bits in used&to be updated 
                    bit=0
                    ovalue=0
                    chg=0 #  bit change flag
                    #mba and regadd are known
                    if srow[0]<>'':
                        bit=int(srow[0]) # bit 0..15
                    if srow[1]<>'':
                        ovalue=int(srow[1]) # bit 0..15
                    #print 'decoding value from bit',bit
                    value=(tcpdata&2**bit)/2**bit # bit value 0 or 1 instead of 1, 2, 4... / added 06.04
                    
                    # check if outputs must be written
                    if value <> ovalue: # change detected, update dichannels value, chg-flag  - saaks ka maski alusel!!!
                        chg=3 # 2-bit change flag, bit 0 to send and bit 1 to process, to be reset separately
                        #ichg=ichg+2**bit # adding up into the change mask
                        msg='DIchannel '+str(mba)+'.'+str(regadd)+' bit '+str(bit)+' change! was '+str(ovalue)+', became '+str(value) # temporary
                        print(msg)
                        log2file(msg)
                        # dichannels table update with new bit values and change flags. no status change here. no update if not changed!
                        Cmd3="UPDATE dichannels set value='"+str(value)+"', chg='"+str(chg)+"', ts_chg='"+str(int(ts))+"' where mba='"+str(mba)+"' and regadd='"+str(regadd)+"' and bit='"+str(bit)+"'" # uus bit value ja chg lipp, 2 BITTI!
                        conn3.execute(Cmd3) # write
                
            else: # respcode>0
                tcperr=tcperr+1 # increase error counter
                msg='failed to read di register from '+str(mba)+'.'+str(regadd)
                print(msg) # common problem, keep it shorter
                log2file(msg)
                #if respcode >0:
                    #socket_restart() # close and open tcpsocket
                #    return 2
            
        conn3.commit()  # dichannel-bits transaction end 
        return respcode

    except:
        print 'there was a problem with dichannels data reading or processing!'
        traceback.print_exc()
        sys.stdout.flush()
        time.sleep(1)
        return 5 
    
# read_dichannel_bits() end. FRESHENED DICHANNELS TABLE VALUES AND CGH BITS (0 TO SEND, 1 TO PROCESS)




def make_dichannel_svc(): # di services into to-be-sent buffer table BUT only when member(s) changed or for renotification
    locstring="" # local
    global inumm,ts,ts_inumm,mac #,tcperr
    mba=0 # local here
    val_reg=''
    desc=''
    comment=''
    mcount=0
    ts_created=ts # timestamp
    sumstatus=0 # summary status for a service, based on service member statuses
    chg=0 # status change flag with 2 bits in use!
    value=0
    ts_last=0 # last ime the service member has been reported to the server
    try:
        Cmd3="BEGIN IMMEDIATE TRANSACTION" # conn3 transaction, dichannels
        conn3.execute(Cmd3) # dichannels
        conn1.execute(Cmd3) # buff2server
        
        Cmd3="select val_reg,max((chg+0) & 1),min(ts_msg+0) from dichannels where ((chg+0 & 1) and ((cfg+0) & 16)) or ("+str(int(ts))+">ts_msg+"+str(renotifydelay)+") group by val_reg"  
        # take into account cfg! not all changes are to be reported immediately! cfg is also for application needs, not only monitoring!
        cursor3.execute(Cmd3)
        
        for row in cursor3: # services to be processed. either just changed or to be resent
            lisa='' # string of space-separated values
            val_reg=''  
            sta_reg=''
            sumstatus=0 # at first

            val_reg=row[0] # service name
            chg=int(row[1]) # change bitflag here, 0 or 1
            ts_last=int(row[2]) # last reporting time
            if chg == 1: # message due to bichannel state change
                print 'DI service to be reported due to change:',val_reg # ,'while last reporting was',ts-ts_last,'s ago, ts now=',ts
            else:
                print 'DI service',val_reg,'to be REreported, last reporting was',ts-ts_last,'s ago' # , ts now=',ts
                
            #mcount=int(row[1]) # changed service member count
            sta_reg=val_reg[:-1]+"S" # service status register name
            svc_name='' # unused? but must exist for insertion int obuff2server
            #print 'reading dichannels values for val_reg',val_reg,'with',mcount,'changed members' # debug 
            Cmd3="select * from dichannels where val_reg='"+val_reg+"' order by member asc" # data for one service ###########
            cursor3a.execute(Cmd3)
            
            for srow in cursor3a: # ridu tuleb nii palju kui selle teenuse liikmeid, pole oluline milliste mba ja readd vahele jaotatud
                #print 'row in cursor3a',srow # temporary debug
                mba=0 # local here
                regadd=0
                bit=0 # 
                member=0
                cfg=0
                ostatus=0 # previous value
                #tvalue=0 # test
                oraw=0
                ovalue=0 # previous or averaged value
                ots=0 # previous status
                avg=0 # averaging strength, has effect starting from 2
                desc=''
                comment=''
                # 0      1   2     3     4      5     6     7     8    9  10     11  
                #mba,regadd,bit,val_reg,member,cfg,block,value,status,ts,desc,comment # dichannels
                if srow[0]<>'':
                    mba=int(srow[0])
                if srow[1]<>'':
                    regadd=int(srow[1]) # must be int! can be missing
                if srow[2]<>'':
                    bit=int(srow[2])
                val_reg=srow[3] #  string
                if srow[4]<>'':
                    member=int(srow[4])
                if srow[5]<>'':
                    cfg=int(srow[5]) # configuration byte 
                # block?? to p[revent sending service with errors. to be added!
                if srow[7]<>'': 
                    value=int(srow[7]) # new value
                if srow[8]<>'':
                    ostatus=int(srow[8]) # old status
                if srow[9]<>'': 
                    ots=int(srow[9]) # value ts timestamp
                #if srow[10]<>'':
                    #ots=int(srow[10]) 
                desc=srow[11] # description for UI
                comment=srow[11] # comment internal

            
                #print 'make_channel_svc():',val_reg,'member',member,'value before status proc',value  # temporary debug
               
                if lisa<>"": # not the first member any nmore
                    lisa=lisa+" "
                    
                # status and inversions according to configuration byte
                status=0 # initially for each member
                if (cfg&4): # value2value inversion
                    value=(1^value) # possible member values 0 voi 1
                lisa=lisa+str(value) # adding possibly inverted member value to multivalue string
                
                if (cfg&8): # value2status inversion
                    value=(1^value) # member value not needed any more
                
                if (cfg&1): # status warning if value 1
                    status=value # 
                if (cfg&2): # status critical if value 1
                    status=2*value 
                
                if status>sumstatus: # summary status is defined by the biggest member sstatus
                    sumstatus=status # suurem jaab kehtima
               
                #print 'make_channel_svc():',val_reg,'member',member,'value after status proc',value,'status',status,'sumstatus',sumstatus  # temporary debug
               
                                        
                #dichannels table update with new chg ja status values. no changes for values! chg bit 0 off! set ts_msg!
                Cmd3="UPDATE dichannels set status='"+str(status)+"', ts_msg='"+str(int(ts))+"', chg='"+str(chg&2)+"' where val_reg='"+val_reg+"' and member='"+str(member)+"'" 
                # bit0 from change flag stripped! this is to notify that this service is sent (due to change). may need other processing however.
                #print Cmd3 # di reporting debug
                conn3.execute(Cmd3) # kirjutamine
                    
                   
                    
            # sending service data into buffer table when the loop above is finished - only if they are up to date, according to ts_created
            if sta_reg == val_reg: # only status will be sent!
                val_reg=''
                lisa=''
                
            #print mac,host,udpport,svc_name,sta_reg,status,val_reg,lisa,ts_created,inumm # temporary
            Cmd1="INSERT into buff2server values('"+mac+"','"+host+"','"+str(udpport)+"','"+svc_name+"','"+sta_reg+"','"+str(sumstatus)+"','"+val_reg+"','"+str(lisa)+"','"+str(int(ts_created))+"','','')" 
            #print "di Cmd1=",Cmd1 # debug
            conn1.execute(Cmd1) # kirjutamine
 
        
        conn1.commit() # buff2server
        conn3.commit() # dichannels transaction end
            
    except: 
        print 'problem with reading dichannels'
        sys.stdout.flush()
        #time.sleep(1)
        #traceback.print_exc()
        
#make_dichannel_svc() lopp





    
def read_counters(): # counters, usually 32 bit / 2 registers.
    locstring="" # see on siin lokaalne!
    global inumm,ts,ts_inumm,mac,tcpdata,tcperr #,MBsta
    respcode=0
    mba=0 # lokaalne siin
    val_reg=''
    sta_reg=''
    status=0
    value=0
    lisa=''
    svc_name='' # tegelikult ei kasuta?
    desc=''
    comment=''
    mcount=0
    Cmd1='' 
    ts_created=ts # selle loeme teenuse ajamargiks
    
    try:
        Cmd3="BEGIN IMMEDIATE TRANSACTION" # conn3
        conn3.execute(Cmd3)
        
        Cmd3="select val_reg,count(member) from counters group by val_reg"
        #print "Cmd3=",Cmd3
        cursor3.execute(Cmd3) # getting services to be read and reported
        
        for row in cursor3: # multivalue service members
            lisa='' # string to put space-separated values in
            val_reg=''  
            sta_reg=''
            status=0 # 
            value=0

            val_reg=row[0] # service value register name
            mcount=int(row[1]) # pole vajalik?
            sta_reg=val_reg[:-1]+"S" # status register name
            svc_name='' # unused?
            #print 'reading counter values for val_reg',val_reg,'with',mcount,'members' # temporary
            Cmd3="select * from counters where val_reg='"+val_reg+"'" #
            #print Cmd3 # temporary
            cursor3a.execute(Cmd3)
            
            for srow in cursor3a: # one row as a result
                #print srow # temporary
                mba=0 # local here
                regadd=0
                member=0
                cfg=0
                x1=0
                x2=0
                y1=0
                y2=0
                outlo=0
                outhi=0
                ostatus=0 # eelmine
                #tvalue=0 # test
                raw=0 # unconverted reading
                oraw=0 # previous unconverted reading
                ovalue=0 # previous converted value
                ots=0
                avg=0 # averaging strength, effective from 2
                desc='' # description for UI
                comment='' # comment internal
                # 0       1     2     3     4   5  6  7  8  9    10     11  12    13   14   15    16  17   18
                #mba,regadd,val_reg,member,cfg,x1,x2,y1,y2,outlo,outhi,avg,block,raw,value,status,ts,desc,comment  # counters
                if srow[0]<>'':
                    mba=int(srow[0]) # modbus address
                if srow[1]<>'':
                    regadd=int(srow[1]) # must be int! can be missing
                val_reg=srow[2] # string
                if srow[3]<>'':
                    member=int(srow[3])
                if srow[4]<>'':
                    cfg=int(srow[4]) # config byte
                if srow[5]<>'':
                    x1=int(srow[5])
                if srow[6]<>'':
                    x2=int(srow[6])
                if srow[7]<>'':
                    y1=int(srow[7])
                if srow[8]<>'':
                    y2=int(srow[8])
                if srow[9]<>'':
                    outlo=int(srow[9])
                if srow[10]<>'':
                    outhi=int(srow[10])
                if srow[11]<>'':
                    avg=int(srow[11])  #  averaging strenght, effective from 2
                #if srow[12]<>'': # block
                #    block=int(srow[12]) # block / error count
                if srow[13]<>'': # previous raw reading
                    oraw=int(srow[13])
                if srow[14]<>'': # previous converted value
                    ovalue=int(srow[14])
                if srow[15]<>'':
                    ostatus=int(srow[15])
                if srow[16]<>'':
                    ots=int(srow[16])
                desc=srow[17]
                comment=srow[18]
                wcount=srow[19] # word count - to be used as read_register() param 3
            
                if mba>=0 and mba<256 and regadd>=0 and regadd<65536:  # legal values for mba and regaddr
                    #print 'reading counter value from mba',mba,'regadd',regadd,'for val_reg',val_reg,'member',member,'wcount',wcount,  # debug
                    
                    respcode=read_register(mba,regadd,wcount)
                    #MBsta[mba-1]=respcode
                    if respcode == 0: # got tcpdata as counter value
                        #use wcount -2 for word order LSW MSW in response (barix barionet)!
                        tcperr=0
                        raw=tcpdata # let's keep the raw
                        value=tcpdata # will be converted later
                        if lisa<>"":
                            lisa=lisa+" "
                            
                        # CONFIG BYTE BIT MEANINGS
                        # 1 - below outlo warning, 
                        # 2 - below outlo critical, 
                        # NB! 3 - not to be sent  if value below outlo
                        # 4 - above outhi warning
                        # 8 - above outhi critical
                        
                        # 16 - to be zeroed regularly, see next bits for when
                        # 32  - midnight if 1, month change if 0
                        # 64 - power to be counted based on count increase and time period between counts
                        # 128 reserv / lsw, msw jarjekord? nagu barix voi nagu android io
                        
                        #kontrolli kas kumulatiivne, nullistuv voi voimsus!
                        if (cfg&16): # power, increment to be calculated! divide increment to time from the last reading to get the power
                            if oraw>0: # last reading seems normal
                                value=raw-oraw # RAW vahe leitud
                                print 'counter raw inc',value, # temporary
                                value=float(value/(ts-ots)) # power reading
                                print 'timeperiod',ts-ots,'raw/time',value # temporary
                                # end special processing for power 
                            else:
                                value=0
                                status=3 # not to be sent
                                print 'probably first run, no power calc result for',val_reg,'this time! value=0, status=3' # vaartuseks saadame None
                                
                        if x1<>x2 and y1<>y2: # seems like normal input data 
                            value=(value-x1)*(y2-y1)/(x2-x1)
                            value=int(y1+value) # integer values to be reported only 
                        else:
                            print "read_counters val_reg",val_reg,"member",member,"ai2scale PARAMETERS INVALID:",x1,x2,'->',y1,y2,'conversion not used!'
                            # jaab selline value nagu oli
                        
                        print 'counter raw',tcpdata,', converted value',value,', oraw',oraw,', ovalue',ovalue,', avg',avg, # the same line continued with next print
                        
                        if avg>1 and abs(value-ovalue)<value/2:  # averaging the readings. big jumps (more than 50% change) are not averaged.
                            value=int(((avg-1)*ovalue+value)/avg) # averaging with the previous value, works like RC low pass filter
                            print ', averaged value',value # ,'rawdiff',abs(raw-oraw),'raw/2',raw/2
                        else:
                            print ', no averaging, value becomes',value
                            
                        
                        # check limits and set statuses based on that
                        # returning to normal with hysteresis, take previous value into account
                        status=0 # initially for each member
                        if value>outhi: # yle ylemise piiri
                            if (cfg&4) and status == 0: # warning if above the limit
                                status=1
                            if (cfg&8) and status<2: # critical if  above the limit
                                status=2
                            if (cfg&12): # unknown if  above the limit
                                status=3
                        else: # return to normal with hysteresis
                            if value<outhi-0.05*(outhi-outlo):
                                status=0 # normal again
                        
                        if value<outlo: # below lo limit
                            if (cfg&3) and status == 0: # warning if below lo limit
                                status=1
                            if (cfg&3) and status<2: # warning  if below lo limit
                                status=2
                            if (cfg&3): # unknown  if below lo limit
                                status=3
                        else: # return
                            if value>outlo+0.05*(outhi-outlo):
                                status=0 # normal again
                                
                        #print 'status for counter svc',val_reg,status,'due to cfg',cfg,'and value',value,'while limits are',outlo,outhi # debug
                        
                        if value<ovalue and ovalue < 4294967040: # counter content lost due to PIC reset. new value cannot be less than existing unless close to 4294967295 (32 bits)
                            value=ovalue+value # restoring based on ovalue and new count
                            print 'restoring lost content for counter',mba,regadd,wcount
                            if wcount == 2: # normal counter
                                write_register(mba,regadd,(value&4294901760)/65536,0) # MSW
                                write_register(mba,regadd+1,(value&65535),0) # LSW
                            else: 
                                if wcount == -2: # barionet counter, MSW must be written first
                                    write_register(mba,regadd+1,(value&4294901760)/65536,0) # MSW
                                    write_register(mba,regadd,(value&65535),0) # LSW
                                else:
                                    print 'illegal counter configuration!',mba,regadd,wcount
                                    
                        #counters table update
                        Cmd3="UPDATE counters set status='"+str(status)+"', value='"+str(value)+"', raw='"+str(raw)+"', ts='"+str(int(ts))+"' where val_reg='"+val_reg+"' and member='"+str(member)+"'" 
                        #print Cmd3 # temporary
                        conn3.execute(Cmd3) # update counters
                                                
                        lisa=lisa+str(value) # members together into one string
                        
                                                
                    else: # register read failed, respcode>0
                        tcperr=tcperr+1
                        print 'failed reading counter register',mba,regadd
                            
                else:
                    print 'invalid mba / regadd',mba,'/',regadd 
                    
        # sending in to buffer 
        #print mac,host,udpport,svc_name,sta_reg,status,val_reg,lisa,ts_created,inumm # temporary
        Cmd1="INSERT into buff2server values('"+mac+"','"+host+"','"+str(udpport)+"','"+svc_name+"','"+sta_reg+"','"+str(status)+"','"+val_reg+"','"+str(lisa)+"','"+str(int(ts_created))+"','','')" 
        # inum and ts_tried empty a t first!
        #print "cnt Cmd1=",Cmd1 # debug
        conn1.execute(Cmd1)
            
                
                
        conn3.commit() # counters transaction end
        conn1.commit() # buff2server transaction end
        return respcode
        
    except: # end reading counters
        print 'problem with counters read or processing'
        traceback.print_exc() 
        sys.stdout.flush()
        time.sleep(1)
        return 5
        
#read_counters end #############
 
 
        
    

def report_setup(): # send setup data to server via buff2server table as usual. 
    locstring="" # local
    global inumm,ts,ts_inumm,mac,host,udpport,TODO,sendstring # 
    mba=0 # lokaalne siin
    reg=''
    reg_val=''
    Cmd1=''
    Cmd4='' 
    ts_created=ts
    svc_name='setup value'
    oldmac=''
    
    sendstring=sendstring+"AVV:"+APVER+"\nAVS:0\n"  # program version written into the code
    udpsend(inumm,int(ts)) # sending to the monitoring server
    
    try:
        Cmd4="BEGIN IMMEDIATE TRANSACTION" # conn4 asetup
        conn4.execute(Cmd4)
        Cmd1="BEGIN IMMEDIATE TRANSACTION" # conn1 buff2server
        conn1.execute(Cmd1)
        
        if mac == '000000000000': # no valid controller id value yet, startup phase!
            Cmd4="select register,value from setup where register='S200'" # find out the correct first!
        else:
            Cmd4="select register,value from setup" # no multimember registers for setup!
        #print Cmd4 # temporary
        cursor4.execute(Cmd4)
        
        for row in cursor4: # 
            val_reg=''  # string
            reg_val=''  # string
            status=0 # esialgu
            #value=0

            val_reg=row[0] # muutuja  nimi
            reg_val=row[1] # string even if number!
            print ' setup variable',val_reg,reg_val
            
            # sending to buffer, no status counterparts! status=''
            Cmd1="INSERT into buff2server values('"+mac+"','"+host+"','"+str(udpport)+"','"+svc_name+"','','','"+val_reg+"','"+reg_val+"','"+str(int(ts_created))+"','','')" 
            # panime puhvertabelisse vastuse ootamiseks. inum ja ts+_tried esialgu tyhi! ja svc_name on reserviks! babup vms... # statust ei kasuta!!
            #print "stp Cmd1=",Cmd1 # temporary debug
            conn1.execute(Cmd1)
              
            if 'S200' in val_reg: # mac stored temporarely instead of discovery
                oldmac=mac
                mac=reg_val
                print 'controller id set to',mac,', was',oldmac
                
                
        conn1.commit() # buff2server trans lopp
        conn4.commit() # asetup trans lopp
        msg='setup reported at '+str(int(ts))
        print(msg)
        log2file(msg) # log message to file  
        sys.stdout.flush()
        time.sleep(0.5)
        return 0
            
    except: # setup reading  problem
        print 'problem with setup reading',Cmd4
        traceback.print_exc()
        sys.stdout.flush()
        msg='setup reporting failure (setup reading problem) at '+str(int(ts))
        print(msg)
        log2file(msg) # log message to file  
        sys.stdout.flush()
        time.sleep(1)
        return 1
    
#report_setup lopp#############
    
 
 
def report_channelconfig(): #report *channels cfg part as XYn for each member to avoid need for sql file dump and push
    global mac,host,udpport,ts
    locstring="" # local
    global inumm,ts,ts_inumm,mac,host,udpport,TODO,sendstring # 
    mba=0 # lokaalne siin
    reg=''
    regadd=''
    #reg_val=''
    Cmd3=''
    Cmd4='' 
    ts_created=ts
    desc=''
    svc_name='' # not needed in fact
    #svc_name='setup value'
    avg=0
    x1=0
    x2=0
    y1=0
    y2=0
    outlo=0
    outhi=0
    cfg=0
    
    try:
        Cmd3="BEGIN IMMEDIATE TRANSACTION" # conn3 modbus_channels
        conn3.execute(Cmd3)
        Cmd1="BEGIN IMMEDIATE TRANSACTION" # conn1 buff2server
        conn1.execute(Cmd1)
        
        Cmd3="select mba,regadd,bit,val_reg,member,cfg,desc from dichannels"
        #             0    1     2     3       4     5   6
        cursor3.execute(Cmd3)
        for row in cursor3: # dichannels members to be reported
            if row[0]<>'':
                mba=int(row[0])
            if row[1]<>'':
                regadd=int(row[1])
            else:
                regadd=0
            if row[2]<>'':
                bit=int(row[2])
            val_reg=row[3]
            if row[4]<>'':
                member=int(row[4])
            if row[5]<>'':
                cfg=int(row[5])
            desc=row[6]
            reg=val_reg[:-1]+str(member) # konfiregister state tabelis sailitamiseks
            reg_val=str(mba)+','+str(regadd)+','+str(bit)+','+str(cfg)+','+desc # comma separated string containing the most important setup values
            #print 'channelreport di reg val',reg,reg_val # debug
            Cmd1="INSERT into buff2server values('"+mac+"','"+host+"','"+str(udpport)+"','"+svc_name+"','','','"+reg+"','"+reg_val+"','"+str(int(ts_created))+"','','')" 
            #print "report_channelconfig Cmd1=",Cmd1 # temporary debug
            conn1.execute(Cmd1) # buff2server
            
        # mba,regadd,val_reg,member,cfg,x1,x2,y1,y2,outlo,outhi,avg,block,raw,value,status,ts,desc
        Cmd3="select mba,regadd,val_reg,member,cfg,x1,x2,y1,y2,outlo,outhi,avg,desc from aichannels"
        #             0      1    2        3     4  5  6  7  8  9     10    11  12  
        cursor3.execute(Cmd3)
        for row in cursor3: # aichannels members to be reported
            if row[0]<>'':
                mba=int(row[0])
            if row[1]<>'':
                regadd=int(row[1])
            else:
                regadd=0
            val_reg=row[2]
            if row[3]<>'':
                member=int(row[3])
            if row[4]<>'':
                cfg=int(row[4])
            if row[5]<>'':
                x1=int(row[5])
            if row[6]<>'':
                x2=int(row[6])
            if row[7]<>'':
                y1=int(row[7])
            if row[8]<>'':
                y2=int(row[8])
            if row[9]<>'':
                outlo=int(row[9])
            if row[10]<>'':
                outhi=int(row[10])
            if row[11]<>'':
                avg=int(row[11])
            desc=row[12]
            reg=val_reg[:-1]+str(member) # konfiregister state tabelis sailitamiseks
            reg_val=str(mba)+','+str(regadd)+','+str(cfg)+','+str(x1)+','+str(x2)+','+str(y1)+','+str(y2)+','+str(outlo)+','+str(outhi)+','+desc # comma separated string containing the most important setup values
            #print 'channelreport ai reg val',reg,reg_val # debug
            
            Cmd1="INSERT into buff2server values('"+mac+"','"+host+"','"+str(udpport)+"','"+svc_name+"','','','"+reg+"','"+reg_val+"','"+str(int(ts_created))+"','','')" 
            #print "report_channelconfig Cmd1=",Cmd1 # temporary debug
            conn1.execute(Cmd1) # buff2server
            
        conn1.commit()  # buff2server transaction end
        conn3.commit()  # modbus_channels transaction end
        return 0

    except: # channels config reading  problem
        print 'problem with channelconfig reading',Cmd4
        traceback.print_exc()
        sys.stdout.flush()
        msg='channelconfig reporting problem at '+str(int(ts))
        print(msg)
        log2file(msg) # log message to file  
        sys.stdout.flush()
        time.sleep(1)
        return 1
 


 
def log2file(msg): # appending a line to the log file
    #rotation should be added if the file becomes too big
    global LOG, ts
    msg=msg+"\n" # add newline to the end
    try:
        with open(LOG,"a") as f:
            f.write(msg) # writing 
        return 0
    except:
        print 'logging problem to',LOG
        traceback.print_exc()
        sys.stdout.flush()
        time.sleep(1)
        return 1
        
        
        
   
def unsent():  # delete unsent for too long messages - otherwise the udp messages will contain old key:value duplicates!
    global ts,MONTS,retrydelay
    delcount=0
    mintscreated=ts
    maxtscreated=ts
    Cmd1="BEGIN IMMEDIATE TRANSACTION"  # buff2server
    conn1.execute(Cmd1)
    #Cmd1="SELECT inum,svc_name,sta_reg,status,val_reg,value,ts_created,ts_tried from buff2server where ts_created+0<"+str(ts+3*renotifydelay) # yle 3x regular notif
    Cmd1="SELECT count(sta_reg),min(ts_created),max(ts_created) from buff2server where ts_created+0+"+str(3*retrydelay)+"<"+str(ts) # yle 3x regular notif
    #print Cmd1 # korjab ka uued sisse!
    cursor1.execute(Cmd1)
    #conn1.commit()
    for rida in cursor1: # only one line for count if any at all
        delcount=rida[0] # int
        if delcount>0: # stalled services found
            #print repr(rida) # debug
            mintscreated=int(rida[1])
            maxtscreated=int(rida[2])
            print delcount,'services lines waiting ack for',3*retrydelay,'s to be deleted' 
            
            #Cmd1="SELECT inum,svc_name,sta_reg,status,val_reg,value,ts_created,ts_tried from buff2server where ts_created+0+"+str(3*retrydelay)+"<"+str(ts) # debug
            #cursor1.execute(Cmd1) # debug
            #for rida in cursor1: # debug
            #    print repr(rida) # debug
    
            Cmd1="delete from buff2server where ts_created+0+"+str(3*retrydelay)+"<"+str(ts)
            conn1.execute(Cmd1)
    
    Cmd1="SELECT count(sta_reg),min(ts_created),max(ts_created) from buff2server"
    cursor1.execute(Cmd1)
    for rida in cursor1: # only one line for count if any at all
        delcount=rida[0] # int
    if delcount>50: # delete all!
        Cmd1="delete from buff2server"
        conn1.execute(Cmd1)
        msg='deleted '+str(delcount)+' unsent messages from buff2server!' 
        print(msg)
        log2file(msg)
    conn1.commit() # buff2server transaction end
        
#unsent() end    
 

 
def udpmessage(): # udp message creation based on  buff2server data, does the retransmits too if needed. 
    # buff2server rows will be deleted and inserted into sent2buffer table based on in: contained in ack message 
    # what happens in case of connectivity loss?
    # inumm on global in: to be sent, inum on global in: to be received in ack
    # 16.03.2013 switching off saving to sent2server! does not work and not really needed! logcat usable as replacement.
    # DO NOT SEND IF STATUS == 3! WILL BE DELETED LATER BUT WILL BE VISIBLE THEN...
    
    #print '----udpmessage start' # debug
    timetoretry=0 # local
    ts_created=0 # local
    svc_count=0 # local
    global sendstring,ts,inumm,ts_inumm  # inumm vaja suurendada enne saatmist, et samaga ei saaks midagi baasi lisada
    locnumm=0 # 
    
    
    timetoretry=int(ts-retrydelay) # send again services older than that
    #print "udpmessage: timetoretry",timetoretry
    Cmd="BEGIN IMMEDIATE TRANSACTION" # buff2server
    conn1.execute(Cmd)
    
    #Cmd1="DELETE * from buff2server where ts_created+60<"+str(int(ts)) # deleting too old unsent stuff, not deleted by received ack / NOT NEEDED ANY MORE
    #conn1.execute(Cmd)
    # instead of or before deleting the records could be moved to unsent2server table (not existing yet). dumped from there, to be sent later as gzipped sql file
    
    # limit 30 lisatud 19.06.2013
    Cmd1="SELECT * from buff2server where ts_tried='' or (ts_tried+0>1358756016 and ts_tried+0<"+str(timetoretry)+") AND status+0<>3 order by ts_created asc limit 30"  # +0 to make it number! use no limit!
    #print "send Cmd1=",Cmd1 # debug
    try:
        cursor1.execute(Cmd1)
        for srow in cursor1:
            if svc_count == 0: # on first row let's increase the inumm!
                inumm=inumm+1 # increase the message number / WHY HERE? ACK WILL NOT DELETE THE ROWS!
                if inumm > 65535:
                    inumm=1 # avoid zero for sending
                    ts_inumm=ts # time to set new inumm value
                    print "appmain: inumm increased to",inumm # DEBUG
                    
            svc_count=svc_count+1
            sta_reg=srow[4]
            status=srow[5]
            val_reg=srow[6]
            value=srow[7]
            ts_created=int(srow[8]) # no decimals needed, .0 always anyway
             
            if val_reg<>'':
                sendstring=sendstring+val_reg+":"+str(value)+"\n"
            if sta_reg<>'':
                sendstring=sendstring+sta_reg+":"+str(status)+"\n"
            
            #lugesime read mis tuleb saata ja muutsime nende ts ning inumm    
            #print 'udpmessage on svc',svc_count,sta_reg,status,val_reg,value,ts_created # temporary     
            
            Cmd1="update buff2server set ts_tried='"+str(int(ts))+"',inum='"+str(inumm)+"' where sta_reg='"+sta_reg+"' and status='"+str(status)+"' and ts_created='"+str(ts_created)+"'" # muudame proovimise aega koigil korraga
            #print "update Cmd1=",Cmd1 
            conn1.execute(Cmd1)
                
        if svc_count>0: # there is something (changed services) to be sent!
            #print svc_count,"services using inumm",inumm,"to be sent now, at",ts # debug
            udpsend(inumm,int(ts)) # sending away inside udpmessage()
        
        Cmd1="SELECT count(mac) from buff2server"  # unsent row (svc member) count in buffer
        cursor1.execute(Cmd1) # 
        for srow in cursor1:
            svc_count2=int(srow[0]) # total number of unsent messages
            
        if svc_count2>30: # do not complain below 30
            print svc_count2,"SERVICE LINES IN BUFFER waiting for ack from monitoring server"
 
    except: # buff2server reading unsuccessful. unlikely...
        print 'problem with buff2serverr read'
        traceback.print_exc()
        sys.stdout.flush()
        time.sleep(1)
        
        
    conn1.commit() # buff2server transaction end   

# udpmessage() end
##################    
    
   


    
def udpsend(locnum,locts): # actual udp sending, adding ts to in: for some debugging reason. if locnum==0, then no in: will be sent
    global sendstring,mac,TCW, ts_udpsent, stop
    if sendstring == '': # nothing to send
        print 'udpsend(): nothing to send!'
        return 1
    
    if len(mac)<>12:
        print 'invalid mac',mac
        time.sleep(2)
        return 1 # do not send messages with invalid mac
        
    sendstring="id:"+mac+"\n"+sendstring # loodame, et ts_created on enam-vahem yhine neil teenustel...
    if locnum >0: # in: to be added
        sendstring="in:"+str(locnum)+","+str(locts)+"\n"+sendstring
        
    TCW[1]=TCW[1]+len(sendstring) # adding to the outgpoing UDP byte counter
    
        
    try:
        UDPSock.sendto(sendstring,saddr)  
        sendlen=len(sendstring)
        #print "sent len",sendlen,"with in:"+str(locnum),sendstring[:66],"..." #sendstring
        msg='\nsent '+sendstring.replace('\n',' ')   # show as one line
        print(msg)
        log2file(msg)
        sendstring=''
        ts_udpsent=ts # last successful udp send
    except:
        #print "udp send failure for udpmessage!"
        stop=1 # better to be restarted due to udp send failure
        msg='script will be stopped due to UDPsock.sendto() failure at '+str(int(ts))
        log2file(msg) # log message to file  
        print(msg)
        traceback.print_exc() # no success for sending
        sys.stdout.flush()
        time.sleep(1)
    
    #if ts-ts_boot>250: # ajutine test stop moju kohta  # tmp debug start
    #    stop=1
    #    print 'testing stop' # tmp debug end
        
        

def pull(filename,filesize,start): # uncompressing too if filename contains .gz and succesfully retrieved. start=0 normally. higher with resume.
    global SUPPORTHOST #
    oksofar=1 # success flag    
    filename2='' # for uncompressed from the downloaded file
    filepart=filename+'.part' # temporary, to be renamed to filename when complete
    filebak=filename+'.bak' 
    dnsize=0 # size of downloaded file
    if start>filesize:
        msg='pull parameters: file '+filename+' start '+str(start)+' above filesize '+str(filesize)
        print(msg)
        log2file(msg)
        return 99 # illegal parameters or file bigger than stated during download resume
        
    req = urllib2.Request('http://'+SUPPORTHOST+'/'+filename)
    #req.headers['Range'] = 'bytes=%s-%s' % (start, start+10000) # TEST to get piece by piece. bytes numbered from 0!
    req.headers['Range'] = 'bytes=%s-' % (start) # get from start until the end.  possible to continue in a loop if needed using 3G
    msg='trying to retrieve file '+SUPPORTHOST+'/'+filename+' from byte '+str(start)
    print(msg)
    log2file(msg)
    try:
        response = urllib2.urlopen(req)
        output = open(filepart,'wb')
        output.write(response.read());
        output.close()
    except:
        msg='pull: partial or failed download of temporary file '+filepart
        print(msg)
        log2file(msg)
        traceback.print_exc()
    try:
        dnsize=os.stat(filepart)[6]  # int(float(subexec('ls -l '+filename,1).split(' ')[4]))
    except:
        msg='pull: got no size for file '+os.getcwd()+'/'+filepart
        print(msg)
        log2file(msg)
        traceback.print_exc()
        oksofar=0
        
    if dnsize == filesize: # ok
        msg='pull: file '+filename+' download OK, size '+str(dnsize)
        TCW[2]=TCW[2]+dnsize # adding tcp_in volume to the traffic counter. failed trial not to be counted? partials will add up to the same number anyway.
        print(msg)
        log2file(msg)
        
        try:
            os.rename(filename, filebak) # keep the previous version if exists
            msg='renamed '+filename+' to '+filebak
        except:
            msg='FAILED to rename '+filename+' to '+filebak
            oksofar=0
            
        print(msg)
        log2file(msg)
        
        try:    
            os.rename(filepart, filename) #rename filepart to filename2
            msg='renamed '+filepart+' to '+filename
        except:
            msg='FAILED to rename '+filepart+' to '+filename
            oksofar=0
        print(msg)
        log2file(msg)
            
        if oksofar == 0: # trouble, exit
            return 1
            
        if '.gz' in filename: # lets unpack too
            filename2=filename.replace('.gz','')
            try:
                os.rename(filename2, filename2+'.bak') # keep the previous versioon if exists
            except:
                pass
                
            try:
                f = gzip.open(filename,'rb')
                output = open(filename2,'wb')
                output.write(f.read());
                output.close() # file with filename2 created
                msg='pull: file '+filename+' unzipped to '+filename2+', previous file kept as '+filebak
            except:
                os.rename(filename2+'.bak', filename2) # restore the previous versioon if unzip failed
                msg='pull: file '+filename+' unzipping failure, previous file '+filename2+' restored'
                traceback.print_exc()
            print(msg)
            log2file(msg)
        
        return 0
    else:
        if dnsize<filesize:
            msg='pull: file '+filename+' received partially with size '+str(dnsize)
            print(msg)
            log2file(msg)
            return 1
        else:
            msg='pull: file '+filename+' received larger than unexpected, in size '+str(dnsize)
            print(msg)
            log2file(msg)
            return 99

# def pull() end. if it was py, reboot should folow. if it was sql, table reread must de done. 
    



def socket_restart(): # close and open tcpsocket
    global tcpaddr, tcpport, tcpsocket, tcperr
    
    try: # close if opened
        #print 'closing tcp socket'
        tcpsocket.close()
        time.sleep(1) 
        
    except:
        print 'tcp socket was not open'
        #traceback.print_exc() # debug
        
    # open a new socket
    try:
        print 'opening tcp socket to modbusproxy,',tcpaddr, tcpport
        tcpsocket = socket(AF_INET,SOCK_STREAM) # tcp / must be reopened if pipe broken, no reusage
        #tcpsocket = socket.socket(AF_INET,SOCK_STREAM) # tcp / must be reopened if pipe broken, no reusage
        tcpsocket.settimeout(5) #  conn timeout for modbusproxy. ready defines another (shorter) timeout after sending!
        tcpsocket.connect((tcpaddr, tcpport)) # leave it connected
        msg='modbusproxy (re)connected at '+str(int(ts))
        print(msg)
        sys.stdout.flush()
        log2file(msg) # log message to file  
        #tcperr=0
        return 0
        
    except:
        print 'modbusproxy socket open failed, to',tcpaddr, tcpport
        #traceback.print_exc() # debug
        sys.stdout.flush() # to see the print lines above in log
        msg='modbusproxy reconnection failed at '+str(int(ts))
        print(msg)
        sys.stdout.flush()
        log2file(msg) # log message to file  
        time.sleep(1)
        return 1
    
        
        

def stderr(message): # for android only? from entry.py of mariusz
    #import sys # already imported
    sys.stderr.write('%s\n' % message)



def array2regvalue(array,reg,stamax): # for reporting variables in arrays, not from channel tables
    member=0
    status=0 # based on value members
    if stamax>2:
        stamax=2 # 2 is max allowed status for nagios
    output=reg+':' # string
    for member in range(len(array)): # 0 1 2 3 
        if output.split(':')[1] <> '': # there are something in sendstring already
            output=output+' '
        output=output+str(array[member])
        #print 'array2regvalue output',output # debug
        if array[member]>status: #
            status=array[member]
    if status>stamax:  
        status=stamax #
    output=output+'\n'+reg[:-1]+'S:'+str(status)+'\n'
    return output
    
    
# ### procedures end ############################################ 
 




 
# #############################################################
# #################### INIT ###################################
# #############################################################


import time
import datetime

#import sqlite3 # in android
#from pysqlite2 import dbapi2 as sqlite3 # obsolete

import os
import sys
import traceback
import subprocess
DEVNULL = open(os.devnull, 'wb') # on python 2.x

#import socket
#from socket import AF_INET, SOCK_DGRAM
from socket import *
import string

#import syslog # only for linux, not android (logcat forwarded to external syslog there)
import select
import urllib2
import gzip
import tarfile
#import logging

host='0.0.0.0' # own ip, should always work to send/receive udp data to the server, without socket binding
tcpaddr=''
tcpport=0
tcpmode=1 # if 0, then no tcpmodbus header needed. crc is never needed.
OSTYPE='' # linux or not?
MBsta=[0,0,0,0] # modbus device states (ability to communicate). 1 = crc error, 2=device error, 3=usb error, 4 proxy conn error
MBoldsta=[1,0,0,0] # previous value, begin with no usb conn
TCW=[0,0,0,0] # array of communication volumes (UDPin, UDPout, TCPin, TCPout), data in bytes. can be restored from server

lockaddr=('127.0.0.1',44444) # only one instance can bind to it
#UDPlockSock = socket.socket(AF_INET,SOCK_DGRAM) # would be better this way...
UDPlockSock = socket(AF_INET,SOCK_DGRAM)
UDPlockSock.settimeout(None)

appdelay=30 # 120 # 1s appmain execution interval, reporting all analogue values and counters. NOT DI channels!! DO NOT REPORT AI EVERY TIME!!!

retrydelay=5 # after 5 s resend is possible if row still in buffer
renotifydelay=240 # send again the DI values after that time period even if not changed. but the changed di and do values are sent immediately!

sendstring="" # datagram to be sent
lisa="" # multivalue string member 
inumm=1 # datagram number 1..65k
inum=0 # returned datagram number to be used in send buffer cleaning
blocklimit=3 # if block reached this then do not send
TODO='' # signal to remember things to do
tcperr=0
ts=0 # timestamp s
ts_created=0 # service creation and inserting into buff2server table
ts_tried=0 # timestamp for last send trial
ts_inumm=0 # inumm changed timestamp. to be increased if tyhe same for too long?
ts_lastappmain=0 # timestamp for last appmain run
ts_lastnotify=0 # timestamp for last messaging out of registers
setup_change=0 # flag setup change
respcode=0 # return code from write_register or send_register, 0=k, 1=tmp failure, 2=lost socket
tcpconnfail=0 # flag about proxy conn
ts_interval1=0 # timestamp of trying to restore modbuysproxy conn interval 1
interval1delay=5 # try to restore modbusproxy connection once in this time period if conn lost
stop=0 # reboot flag
LOG=sys.argv[0].replace('.py','.log') # should appear in the current directory
filename='' # for pull()
tablename='' # for sqlread()
filepart=''
dnsize=0
filesize=0
todocode=0 # return code
#pullcode=0 # return code
startnum=0 # file download pointer
pulltry=1 # counter for pull() retries
cfgnum=1 # config retry counter
ts=time.mktime(datetime.datetime.now().timetuple()) #seconds now, with comma
ts_boot=int(ts) # startimise aeg, UPV jaoks
mac='000000000000' # initial mac to contact the server in case of no valid setup
odiword=-1 # previous di word, on startup do not use         
joru1=''
joru2=''    
fore=''

try:
    OSTYPE=os.environ['OSTYPE'] #  == 'linux': # running on linux, not android
    print 'seems to run on linux'

    try:
        print sys.argv[1],sys.argv[2] # <addr:ip> <sql_dir>
    except:
        print ' / parameters (socket and sql_dir) needed to run on linux!' 
        sys.exit()
        
    try:
        tcpport=int(sys.argv[1].split(':')[1]) # tcpport=502 # std modbusTCP port # set before
        tcpaddr=sys.argv[1].split(':')[0] # "10.0.0.11" # ip to use for modbusTCP
    except:
        print 'invalid address:port given',tcpaddr,tcpport
        sys.exit()
        
    from sqlite3 import dbapi2 as sqlite3 # in linux
    os.chdir(sys.argv[2]) # ('/srv/scada/acomm/sql')
    #print os.getcwd()
    
except: # android
    OSTYPE='android'
    import android 
    droid = android.Android()
    
    from android_context import Context
    import os.path

    import android_network # android_network.py and android_utils.py must be present!
    
    
    tcpport=10502 # modbusproxy
    tcpaddr="127.0.0.1" # localhost ip to use for modbusproxy
    import BeautifulSoup # ? 
    #import gdata.docs.service 
    import termios
    import sqlite3
    os.chdir('/sdcard/sl4a/scripts/d4c')
    #print os.getcwd()
    
print 'current dir',os.getcwd()
    

    
try: # is another copy of this script already running?
    UDPlockSock.bind(lockaddr)
    msg='\n\n'+APVER+' starting at '+str(int(ts))
    log2file(msg)
    print(msg)
    sys.stdout.flush()
    time.sleep(2)

except: # lock active
    print 'lock active, channelmonitor must be running already' # why is there a delay?
    msg='try to start while lock is already active at '+str(int(ts))
    log2file(msg) # log message to file  
    stop=1 # exiting with this below
    UDPlockSock.close()
    # mark this event into the log


if stop == 0: # lock ok
    buf=1024 # udb input
    shost="46.183.73.35" # udp listening server
    udpport=44445 # voib ka samast masinast saata sama ip ja pordi pealt! bindima ei pea!
    saddr=(shost,udpport) # mon server
    # shost ja udpport voiks ka parameetritega olla.

    
    print "SERVER saddr",saddr,', MODBUSPROXY tcpaddr',tcpaddr,tcpport
    
    sys.stdout.flush() # to see the print lines above in log
    time.sleep(1) # start

    tcpwait=2 # alla 0.8 ei tasu, see on proxy tout...  #0.3 # how long to wait for an answer from modbusTCP socket

    UDPSock = socket(AF_INET,SOCK_DGRAM)
    #UDPSock = socket.socket(AF_INET,SOCK_DGRAM) # would be better this way...
    UDPSock.settimeout(0.1) # (0.1) use 1 or more for testing # in () timeout to wait for data from server. defines alsomain loop interval / execution speed!!

    host='0.0.0.0' # own ip for udp, should always work, no need for socket binding
    addr = (host,udpport) # itself
    print 'UDP connection should be OK with',addr


    conn1tables=['buff2server']
    conn3tables=['aichannels','dichannels','dochannels','counters','chantypes','devices']
    conn4tables=['setup']
    
    #create sqlite connections (while located in sql_dir)
    try:
        conn1 = sqlite3.connect('./buff2server',2) # buffer data from modbus registers, unsent or to be resent
        conn3 = sqlite3.connect('./modbus_channels',2) # modbus register related tables / sometimes locked!!
        conn4 = sqlite3.connect('./asetup',2) # setup table, only for update, NO INSERT! 2 s timeout. timeout will cause exexution stop.
        
    except:
        msg=='sqlite connection problem' # should be reported using backdoor connection
        print(msg)
        log2file(msg)
        traceback.print_exc() # sqlite connect failure
        sys.stdout.flush()
        time.sleep(3)

    #conn.execute("PRAGMA journal_mode=wal")  # to speed up
    conn1.execute("PRAGMA synchronous=OFF")  # 
    conn3.execute("PRAGMA synchronous=OFF")  # 
    cursor1=conn1.cursor() # cursors to read data from tables
    #cursor2=conn2.cursor()
    cursor3=conn3.cursor()
    cursor3a=conn3.cursor() # the second cursor for the same connection
    cursor4=conn4.cursor()


    # delete unsent rows older than 60 s
    Cmd1="DELETE from buff2server where ts_created+0<"+str(ts)+"-60" # kustutakse koik varem kui ninute tagasi loodud
    conn1.execute(Cmd1)
    Cmd1="SELECT count(sta_reg) from buff2server" # kustutakse koik varem kui ninute tagasi loodud
    cursor1.execute(Cmd1)
    conn1.commit()
    for row in cursor1:
        print row[0],'svc records to be sent currently in buffer' 
    time.sleep(1) # buff2server delete old if any



    socket_restart() # socket to modbusproxy, first open

    while channelconfig() > 0 and cfgnum<5: # do the setup but not for more than 10 times
        msg='attempt no'+str(cfgnum+1)+' of 5 to contact proxy and configure devices, retrying in 2 seconds'
        print msg
        log2file(msg)
        cfgnum=cfgnum+1
        if socket_restart()>0: # tcp conn to modbusproxy
            MBsta=[2,2,2,2] # no modbus communication possible
            msg='FAILED to connect modbusproxy!'
        else: # socket ok
            msg='modbusproxy connected'
        print msg
        log2file(msg)
        time.sleep(2)
        
    if cfgnum == 5: # failed proxy conn and setup...
        msg='channelconfig() failure! giving up on try '+str(cfgnum)
    else:
        msg='channelconfig() success on try'+str(cfgnum)
        MBsta=[0,0,0,0]        
    print(msg)
    log2file(msg)
    sys.stdout.flush()
    time.sleep(1) #
        
    print 'reporting setup',APVER # must be done twice, the second can be more successful with connection and mac known (tmp hack)
    time.sleep(1)
    report_setup() # sending to server on startup
    SUPPORTHOST='www.itvilla.ee/support/pyapp/'+mac # now there is hope for valid supporthost, not contining pyapp/000000000000

    sendstring=array2regvalue(MBsta,'EXW',2) # adding EXW, EXS to sendstring based on MBsta[]
    sendstring=sendstring+"UPV:0\nUPS:1\nTCW:?\n" # restoring traffic volume from server in case of restart. need to reset it in the beginning of the month.
    udpsend(inumm,int(ts)) # version data # could be put into buff2server too...

    sys.stdout.flush()
    time.sleep(1)

    print 'reporting setup again' # must be done twice, the second can be more successful with connection and mac known (tmp hack)
    report_setup() # sending some data from asetup/setup to server on startup
    report_channelconfig() # sending some data from modbuschannels/*channels to server on startup
    msg='starting the main loop at '+str(int(ts))+'. mac '+mac+', saddr '+str(repr(saddr))+', modbusproxy '+tcpaddr+':'+str(tcpport)
    print(msg)
    log2file(msg) # log message to file  

    
    
    


while stop == 0: # ################  MAIN LOOP BEGIN  ############################################################
    ts=time.mktime(datetime.datetime.now().timetuple()) #seconds now, with comma
    MONTS=str(int(ts)) # as integer, without comma
    
    try: # if anything comes into buffer in 0.1s
        setup_change=0 # flag to detect possible setup changes
        data,raddr = UDPSock.recvfrom(buf)
        TCW[0]=TCW[0]+len(data) # adding top the incoming UDP byte counter
        
        #print "got message from addr ",raddr," at ",ts,":",data.replace('\n', ' ') # showing datagram members received on one line, debug
        #syslog.syslog('<= '+data.replace('\n', ' ')) # also to syslog (communication with server only)
        
        if (int(raddr[1]) < 1 or int(raddr[1]) > 65536):
            msg='illegal source port '+str(raddr[1])+' in the message received from '+raddr[0]
            print(msg)
            log2file(msg)
            
        if raddr[0] <> shost:
            msg='illegal sender '+str(raddr[0])+' of message: '+data+' at '+str(int(ts))  # ignore the data received!
            print(msg)
            log2file(msg)
            data='' # data destroy
            
        if "id:" in data: # mac aadress
            id=data[data.find("id:")+3:].splitlines()[0]
            if id<>mac:
                print "invalid id in server message from ", addr[0] # this is not for us
                data='' # destroy the datagram, could be for another controller behind the same connection
            Cmd1="" 
            Cmd2=""

            if "in:" in data:
                #print 'found in: in the incoming message' # #lines=data[data.find("in:")+3:].splitlines()   # vaikesed tahed
                inum=eval(data[data.find("in:")+3:].splitlines()[0].split(',')[0]) # loodaks integerit
                if inum >= 0 and inum<65536:  # valid inum, response to message sent if 1...65535. datagram including "in:0" is a server initiated "fast communication" message
                    #print "found valid inum",inum,"in the incoming message " # temporary
                    msg='got ack '+str(inum)+' in message: '+data.replace('\n',' ') 
                    print(msg)
                    log2file(msg)
                    
                    Cmd="BEGIN IMMEDIATE TRANSACTION" # buff2server, to delete acknowledged rows from the buffer
                    conn1.execute(Cmd) # buff2server ack transactioni algus, loeme ja kustutame saadetud read
                    
                    Cmd1="SELECT * from buff2server WHERE mac='"+id+"' and inum='"+str(inum)+"'" # matching lines to be moved into sent2server
                    #print "mark as sent: sent Cmd1=",Cmd1
                    Cmd3="DELETE from buff2server WHERE mac='"+id+"' and inum='"+str(inum)+"'"  # deleting all rows where inum matches server ack 
                    # siia voiks  lisada ka liiga vanade kirjete automaatne kustutamine. kui ei saa, siis ei saa!
                    #print "delete: Cmd3=",Cmd3
                    try:
                        cursor1.execute(Cmd1) # selected
                        conn1.execute(Cmd3) # deleted
                    except:
                        print 'problem with',Cmd3
                        traceback.print_exc() 
                        sys.stdout.flush()
                        time.sleep(1)
                        #
                        
                    conn1.commit() # buff2server transaction end 
                    #print "table buff2server cleaning off the members of the message sent with inum",inum,"done" # debug
                    
                    
                    
                    #Cmd="BEGIN IMMEDIATE TRANSACTION" # sent2server transaction / switched off 16.03.2013
                    #conn2.execute(Cmd) #
                    
                    #for row in cursor1: # this is from buff2server
                    #    print "row from buff2server:",repr(row) # for every row in buff2server with given inum add a row into sent2server
                    #    Cmd2="INSERT into sent2server values ('"+row[0]+"','"+row[1]+"','"+row[2]+"','"+row[3]+"','"+row[4]+"','"+row[5]+"','"+row[6]+"','"+row[7]+"','"+row[8]+"','"+row[9]+"','"+row[10]+"','"+MONTS+"')" # ts_ack added
                    #    print "Cmd2=",Cmd2
                     #   try:
                      #      conn2.execute(Cmd2) # add into table sent2server 
                            
                       # except:
                        #    print "trouble with",Cmd2
                         #   traceback.print_exc()                            
                    
                    #conn2.commit() # sent2buffer transaction end - successful communication log, needs to truncated some time!
                    #print "added the members of the message sent with inum",inum,"into sent2server table"
                    


                    #print 'wait a little...' # give some time for sqlite? 
                    #time.sleep(1) # temporary test

                    #temporary check = are the rows really deleted from buff2server and moved into sent2server?
                    Cmd1="SELECT count(inum) from buff2server WHERE mac='"+id+"' and inum='"+str(inum)+"'" 
                    #print Cmd1  # temporary
                    try:
                        cursor1.execute(Cmd1)
                        conn1.commit()
                        for row in cursor1: # should be one row only
                            rowcount1=row[0] #number of rows still there with given inum
                            if row[0]>0:
                                print "ack ERROR: there are still",row[0],"rows in buff2server with inum",inum
                            #else:
                                #print ', rows with inum',inum,'deleted from buff2server' # debug
                    
                    except:
                        print 'trouble with',Cmd1
                        traceback.print_exc()
                        sys.stdout.flush()
                        time.sleep(1)
                        
                            
                    #print 'testing sent2server now'
                    #Cmd2="SELECT count(inum) from sent2server WHERE mac='"+id+"' and inum='"+str(inum)+"' and ts_ack+0>"+str(int(ts-30)) # search from recently added rows
                    #print Cmd2 # temporary
                    #try:
                        #cursor2.execute(Cmd2) # sent2server tabelisse edukalt saadetud teenuseridade lisamine. 
                        #conn2.commit()
                        #for row in cursor2: # should be one row only
                            #if row[0]>0:
                                #print row[0],"rows with inum ",inum,"successfully added into sent2server"
                            #else:
                                #print 'ERROR: no lines with inum',inum,'saved into sent2server!'
                    #except:
                        #print "trouble with",Cmd2
                        #traceback.print_exc()                                
                    # check end
                    


            # from now on we do not care if in: was or was not in the receved datagram

            # #### possible SETUP information contained in received from server message? ########
            # no insert into setup, only update allowed!
            lines=data.splitlines() # all members as pieces again
            
            for i in range(len(lines)): # looking into every member of incoming message
                if ":" in lines[i]:
                    #print "   "+lines[i]
                    line = lines[i].split(':')
                    sregister = line[0] # setup reg name
                    svalue = line[1] # setup reg value
                    if sregister <> 'in' and sregister <> 'id': # others may be setup or command (cmd:)
                        msg='got setup/cmd reg:val '+sregister+':'+svalue  # need to reply in order to avoid retransmits of the command(s)
                        print(msg)
                        log2file(msg)
                        sendstring=sendstring+sregister+":"+svalue+"\n"  # add to the answer
                        udpsend(0,int(ts)) # send the response right away to avoid multiple retransmits
                        time.sleep(0.1)
                        if sregister<>'cmd': # can be variables to be saved into setup table or to be restored. do not accept any setup values that are not in there already!
                            if sregister[0] == 'W' or sregister[0] == 'B' or sregister[0] == 'S': # could be setup variable
                                print 'need for setup change detected due to received',sregister,svalue,', setup_change so far',setup_change
                                if setup_change == 0: # first setup variable in the message found (there can be several)
                                    setup_change=1 # flag it
                                    sCmd="BEGIN IMMEDIATE TRANSACTION" # setup table. there may be no setup changes, no need for empty transactions
                                    try:
                                        conn4.execute(sCmd) # setup transaction start
                                        print 'transaction for setup change started'
                                    except:
                                        print 'setup change problem'
                                        traceback.print_exc()
                                        sys.stdout.flush()
                                        time.sleep(1)
                                        
                                    
                                else: # already started
                                    print 'setup_change continues' # debug

                                
                                sCmd="update setup set value='"+str(svalue)+"', ts='"+str(int(ts))+"' where register='"+sregister+"'" # update only, no insert here!
                                print sCmd # debug
                                try: # 
                                    conn4.execute(sCmd) # table asetup/setup
                                    print 'setup change done',sregister,svalue
                                except: #if not succcessful, then not a valid setup message
                                    print 'assumed setup register',sregister,'not found in setup table! value',svalue,'ignored!'
                                    traceback.print_exc() # temporary debug only
                                    sys.stdout.flush()
                                    time.sleep(1)
                            else: # did not begin with W B S, some program variable to be rrestored?
                                if sregister == 'TCW': # traffic volumes to be restored
                                    if len(svalue.split(' ')) == 4: # member count for traffic: udpin, udpout, tcpin, tcpout in bytes
                                        for member in range(len(svalue.split(' '))): # 0 1 2 3
                                            TCW[member]=int(float(svalue.split(' ')[member]))
                                    msg='restored traffic volume array TCW to'+repr(TCW)
                                    print(msg)
                                    log2file(msg)
                                
                                if sregister == 'ECW': # counter volumes to be restored - sobita counters infoga!
                                    print 'going to set counters 412 and 415' # debug
                                    if len(svalue.split(' ')) == 2: # member count for traffic: udpin, udpout, tcpin, tcpout in bytes
                                        write_register(1,412,(int(float(svalue.split(' ')[0]))&4294901760)/65536,0) # MSW
                                        write_register(1,413,(int(float(svalue.split(' ')[0]))&65535),0) # LSW
                                        write_register(1,414,(int(float(svalue.split(' ')[1]))&4294901760)/65536,0) # MSW
                                        write_register(1,415,(int(float(svalue.split(' ')[1]))&65535),0) # LSW
                                        msg='restored energy counter volume ECW' 
                                        print(msg)
                                        log2file(msg)
                                    
                        else: # must be cmd, not to be saved into setup table
                            msg='remote command '+sregister+':'+svalue+' detected at '+str(int(ts)) 
                            print(msg)
                            log2file(msg)
                            if TODO == '': # no change if not empty
                                TODO=svalue # command content to be parsed and executed
                                print 'TODO set to',TODO
                            else:
                                print 'could not set TODO to',svalue,', TODO still',TODO
                                
                    # all members that are not in or id were added to sendstring above!
                    if sendstring<>'':
                        udpsend(0,int(ts))  # send back the ack for commands. this adds in and id always. no need for server ack, thus 0 instead of inumm
                    
            if setup_change == 1: #there were some changes done  to setup
                conn4.commit() # transaction end for setup change. what if no changes were needed?
                setup_change=0 #back to normal
                if TODO == '':
                    TODO='VARLIST' # let's report setup without asking if setup was changed
                else: # not empty, something still not done?
                    print 'could not set TODO to VARLIST, was not empty:',TODO
                        
            #####
                
            
            
                 
            
        else:
            msg="got illegal message (no id) from "+str(addr)+" at "+str(int(ts))+": "+data.replace('\n',' ')  # missing mac
            print(msg)
            log2file(msg)
            data='' # destroy received data

    except:  # no new data in 0.1s waiting time
        #print '.',  #currently no udp response data on input, printing dot
    
        unsent()  # delete from buff2server the services that are unsent for too long (3*renotifydelay)
        
        #something to do? 
        
        if TODO <> '': # yes, it seems there is something to do
            todocode=todocode+1 # limit the retrycount
            
            if TODO == 'VARLIST':
                todocode=report_setup() # general setup from asetup/setup
                todocode=todocode+report_channelconfig() # iochannels setup from modbus_channels/dichannels, aichannels, counters* - last ytd
                
            if TODO == 'REBOOT': # reboot, just the application or android as well??
                stop=1
                todocode=0
                msg='stopping for reboot due to command at '+str(int(ts))
                print(msg)   
                log2file(msg) # log message to file  
                sys.stdout.flush()
                time.sleep(1)
            
            if TODO == 'CONFIG': # 
                todocode=channelconfig() # configure modbus registers according to W... data in setup
            
            
            if TODO.split(',')[0] == 'pull':
                if len(TODO.split(',')) == 3: # download a file (with name and size given)
                    filename=TODO.split(',')[1]
                    filesize=int(TODO.split(',')[2])
                        
                    if pulltry == 0: # first try
                        pulltry=1 # partial download is possible, up to 10 pieces!
                        startnum=0
                        todocode=1 # not yet 0
                        
                    if pulltry < 10 and todocode >0: # NOT done yet
                        if pulltry == 1: # there must be no file before the first try
                            try:
                                os.remove(filename+'.part')
                            except:
                                pass
                        else: # second and so on try
                            try:
                                filepart=filename+'.part'
                                startnum=os.stat(filepart)[6]
                                msg='partial download size '+str(dnsize)+' on try '+str(pulltry)
                            except:
                                msg='got no size for file '+os.getcwd()+'/'+filepart+', try '+str(pulltry)
                                startnum=0
                                #traceback.print_exc()
                            print(msg)
                            log2file(msg)
                            
                        if pull(filename,filesize,startnum)>0:
                            pulltry=pulltry+1 # next try will follow
                            todocode=1
                        else: # success
                            pulltry=0
                            todocode=0
                else:
                    todocode=1
                    
            if TODO.split(',')[0] == 'push': # upload a file (with name and passcode given)
                filename=TODO.split(',')[1]
                #filesize=int(TODO.split(',')[2])
                #todocode=push(filename,filesize)
            
                        
            if TODO.split(',')[0] == 'sqlread':
                if len(TODO.split(',')) == 2: # cmd:sqlread,aichannels (no extension for sql file!)
                    tablename=TODO.split(',')[1]
                    if '.sql' in tablename:
                        msg='invalid parameters for cmd '+TODO
                        print(msg)
                        log2file(msg)
                        pulltry=88 # need to skip all tries below
                    else:
                        todocode=sqlread(tablename) # hopefully correct parameter (existing table, not sql filename)               
                        if tablename == 'setup' and todocode == 0: # table refreshed, let's use the new setup
                            channelconfig() # possibly changed setup data to modbus registers
                            report_setup() # let the server know about new setup
                else: # wrong number of parameters
                    todocode=1
            
            # start scripts in parallel (with 10s pause in this channelmonitor). cmd:runscript,nimi,0 # 0 or 1 means bg or fore
            # use background normally, the foreground process will open a window and keep it open until closed manually
            if TODO.split(',')[0] == 'run':
                if len(TODO.split(',')) == 3: # run any script in the d4c directory as foreground or background subprocess
                    script=TODO.split(',')[1]
                    if script in os.listdir('/sdcard/sl4a/scripts/d4c'): # file exists
                        fore=TODO.split(',')[2] # 0 background, 1 foreground
                        extras = {"com.googlecode.android_scripting.extra.SCRIPT_PATH":"/sdcard/sl4a/scripts/d4c/%s" % script}
                        joru1="com.googlecode.android_scripting"
                        joru2="com.googlecode.android_scripting.activity.ScriptingLayerServiceLauncher"
                        if fore == '1': # see jatab akna lahti, pohiprotsess kaib aga edasi
                            myintent = droid.makeIntent("com.googlecode.android_scripting.action.LAUNCH_FOREGROUND_SCRIPT", None, None, extras, None, joru1, joru2).result
                        else: # see ei too mingit muud jura ette, toast kaib ainult labi
                            myintent = droid.makeIntent("com.googlecode.android_scripting.action.LAUNCH_BACKGROUND_SCRIPT", None, None, extras, None, joru1, joru2).result
                        try:
                            droid.startActivityIntent(myintent)
                            msg='tried to start'+script
                            if fore == 1:
                                msg=msg+' in foreground'
                            else:
                                msg=msg+' in background'
                            print(msg)
                            log2file(msg)
                            todocode=0
                        except:
                            traceback.print_exc()
                            todocode=1
                        time.sleep(10) # take a break while subprocess is active just in case...
                    else:
                        msg='file not found: '+script
                        print(msg)
                        todocode=1
                        time.sleep(2)
                    if todocode == 0:
                        msg='new sqlite databases created'
                        if script == 'dbREcreate.py': # with this do the new setup as well
                            msg='trying to configure channels and report setup too due to executed script '+script
                            print(msg)
                            log2file(msg)
                            time.sleep(1)
                            channelconfig() # possibly changed setup data to modbus registers
                            report_setup() # let the server know about new setup
                    else:
                        msg='subprocess failure'
                    print(msg)
                    log2file(msg)
                    time.sleep(10)
                else:
                    todocode=1 # wrong number of parameters
            
            if TODO.split(',')[0] == 'size': # run any script in the d4c directory as foreground or background subprocess
                script=TODO.split(',')[1]
                try:
                    dnsize=os.stat(script)[6]
                    todocode=0
                except:
                    todocode=1
            
            
            # common part for all commands below
            if todocode == 0: # success with TODO execution
                msg='remote command '+TODO+' successfully executed'
                if TODO.split(',')[0] == 'size':
                    msg=msg+', size '+str(dnsize)
                sendstring=sendstring+'ERS:0\n'
                TODO='' # no more execution
            else: # no success
                msg='remote command '+TODO+' execution incomplete on try '+str(pulltry)
                sendstring=sendstring+'ERS:2\n'
                if TODO.split(',')[0] == 'size':
                    msg=msg+', file not found'
                if 'pull,' in TODO and pulltry<5: # pull must continue
                    msg=msg+', shall try again TODO='+TODO+', todocode='+str(todocode)
                else: # no pull or enough pulling
                    msg=msg+', giving up TODO='+TODO+', todocode='+str(todocode)
                    TODO=''
            print(msg)
            log2file(msg)            
            sendstring=sendstring+'ERV:'+msg+'\n' # msh cannot contain colon or newline
            udpsend(0,int(ts)) # SEND AWAY. no need for server ack so using 0 instead of inumm
            
            #TODO='' # must be emptied not to stay in loop
            #print 'remote command processing done'
            sys.stdout.flush()
            #time.sleep(1)
        else:
            pulltry=0 # next time like first time
        # ending processing the things to be done


    
    # ####### now other things like making services messages to send to the monitoring server and launching REGULAR MESSANING ########
    ts=time.mktime(datetime.datetime.now().timetuple()) #time in seconds now
        
    # ###### FIRST THE THINGS TO DO MORE OFTEN, TO BE REPORTED ON CHANGE OR renotifydelay TIMEUT (INDIVIDUAL PER SERVICE!) ##########
    time.sleep(0.05) # try to avoid first false di reading after ai readings
    if read_dichannel_bits() ==0: # successful di read as bitmaps from registers. use together with the make_dichannel_svc()!
        make_dichannel_svc() # di related service messages creation, insert message data into buff2server to be sent to the server # tmp OFF!
        write_dochannels() # compare the current and new channels values and use write_register() to control the channels to be changed with 
    
    if MBsta<>MBoldsta: # change to be reported
        print 'change in MBsta, from  to',MBoldsta,MBsta,'at',ts
        sendstring=sendstring+array2regvalue(MBsta,'EXW',2) # EXW, EXS reporting if changed
        MBoldsta=MBsta
    
    #check tcp socket health, restart also if tcperr too high (consecutive errors), once in 5 seconds or so
    if ts>ts_interval1+interval1delay: # not to try too often, deal with other things too
        ts_interval1=ts
        #print 'MBoldsta, MBsta',MBoldsta,MBsta,'at',ts # report once in 5 seconds or so
        if tcperr>4:
            print 'trying to reopen tcpsocket at',ts
            ts_tcprestart=ts
            if socket_restart()>0:
                tcperr=0 # restart counter        
            sys.stdout.flush()
            time.sleep(0.5) # socket restart
        read_aichannels() # read data into sqlite tables
        
    # ### NOW the ai and counter values, to be reported once in 30 s or so
    if ts>appdelay+ts_lastappmain:  # time to read analogue registers and counters, not too often
        # this is the appmain part below
        print "appmain start at",ts,">",appdelay+ts_lastappmain,"appdelay",appdelay
        ts_lastappmain=ts # remember the execution time
  
        make_aichannels_svc() # put ai data into buff2server table to be sent to the server - only if successful reading!
        read_counters() # read counters (2 registers usually, 32 bit) and put data into buff2server table to be sent to the server - only if successful reading!
    
        # ############################################################ temporary check to debug di part here, not as often as normally
        #read_dichannel_bits() # di read as bitmaps from registers. use together with the make_dichannel_svc()!
        #make_dichannel_svc() # di related service messages creation, insert message data into buff2server to be sent to the server
        #write_dochannels() # compare the current and new channels values and use write_register() to control the channels to be changed with 
        # end di part. put into fastest loop for fast reaction!
        # ###########################################################
        
    # ### resending the unchanged di values just to avoid unknown state for them oin nagios, once in 4 minutes or so
    if ts>renotifydelay+ts_lastnotify:  # regular messaging not related to registers but rather to program variables
        print "renotify application variables due to ts",ts,">",renotifydelay+ts_lastnotify,", renotifydelay",renotifydelay
        ts_lastnotify=ts # remember timestamp
        
        sendstring=sendstring+array2regvalue(MBsta,'EXW',2) # EXW, EXS reporting periodical based on MBsta[] for up to 4 modbus addresses
        sendstring=sendstring+array2regvalue(TCW,'TCW',0) # traffic TCW[] reporting periodical, no status above 0
        
        #testdata() # test services / can be used instead of read_*()
        #unsent()  # unsent by now. chk using renotifydelay to send again or delete of too old. vigane! kustutab ka selle, mis on vaja saata!
        
        #if ts>ts_boot + 20: # to avoid double messsaging on startup
        sendstring=sendstring+array2regvalue(MBsta,'EXW',2) # EXW, EXS reporting even if not changed
        sendstring=sendstring+"UPV:"+str(int(ts-ts_boot))+"\nUPS:" # uptime value in seconds
        if int(ts-ts_boot)>1800: # status during first 30 min of uptime is warning, then ok
            sendstring=sendstring+"0\n" # ok
        else:
            sendstring=sendstring+"1\n" # warning
    
    #send it all away, soe mgo via buff2server, some directly from here below
    
    if sendstring<>'': # there is something to send
            udpsend(0,int(ts)) # SEND AWAY. no need for server ack so using 0 instead of inumm

    # REGULAR MESSAGING RELATED PART END (AI, COUNTERS)   

       
        
        
    # control logic FOR OUTPUTS goes to a separate script, manipulating dochannels only. ##################    
    
   
        
    udpmessage() # chk buff2server for messages to send or resend. perhaps not on the fastest possible rate? 
    #but immediately if there as a change in dichannels data. no problems executong every time if select chg is fast enough...
    
    #print '.', # dots are signalling the fastest loop executions here - blue led is better...
    
    sys.stdout.flush() # to update the log for every dot
    

UDPlockSock.close()
msg='script'+sys.argv[0]+' has ended due to stop>0'
print(msg)
log2file(msg)
sys.stdout.flush()
time.sleep(2) 
            
#main end. main frequency is defined by udp socket timeout!
######## END  ######################
