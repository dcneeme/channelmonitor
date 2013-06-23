#!/usr/bin/python

APVER='channelmonitor v0.56' 
# 28.12.2012 midagi teeb, aga sqlite baasidesse midagi ei kirjuta
# 29.12.2012 baasid kuidagi kaima ja protseduurideks jagamine
# 30.12.2012 esmane saatm ine ok, retry veel ei toimi
# 20.01.2013 sidumine modbus lugemisega. esialgu sain valmis lugemise, kuid veel mitte puhvrisse saatmist.
# 21.01.2013 temperatuurid jooksma pandud nagiosse, 46 andurilt kyte koogu 20. lisada UPV (uptime) regulaarne saatmine.
# 04.02.2013 proovin sobitada modbus_channels aichannels failiga. sql transaction kogu read_aichannels ulatuses lopetas jama liikmete 0 ja 1 kordamisega!
# 05.02.1013 loendite lisamine, counters.sql ja read_counters(). voimsused counters baasil! tore. cfg bittide jrk muudatus nii counters kui aichannels, raw tabelitesse juurde.
# 07.02.2013 NaN lisamine puuduva multivalue liikme tahistamiseks - voib ka yks graafiku joon katkeda, ei poe koik...  muuda vastavalt ka nagiosele scripte. Member1= Member2=3
# dichannels kaivitamise algus, read_dichannel_bits() ja make_dichannel_svc()
# 15.02.2013 negatiivsed numbrid (temp jm ai) korda - kui bit16, siis num=num-32768
# 10.02.2013 vastuvoetud info, mis ei ole in: ega id:, panna tabelisse asetup.sql!  counters MSB LSB jrk juhitav wcount abil.
# 19.02.2013 eelmise lopetamine
# 20.02.2013 counters fixed.temperature 256 (raw 4096) to be ignored now! setup table first trials
# 21.02.2013 unsent and resending debug.
# 26.02.2013 setup reporting. notifation interval can be controlled now. named to acomm_srv5.py
# 27.02.2013 setup and remote setup debugged/fixed. DI messaging enabled, but happens too often! should only happen on change and on renotifydelay
# 01.03.2013 dichannels reporting debugging, chk inside appmain part. STILL NOT moving to sent2server! need fotr buff2server deletion even if deleted?? rollback!?
# 16.03.2013 dochannels table and writing coils and registers added, renamed to acomm_srv6.py. output control by updating outchannels table is now possible.
# 18.03.2013 abnormal renotifications debug (the same buff2server lines appear again with next inum again and again). inumm was increased in a wrong way! BUT now no send at all...
# 19.03.2013 almost ok, but dichannels repeated notifications for some reason!
# 22.03.2013 kordusteavitused valja di juurest, teavitab ainult muutusi kui cfg&32. aga renotify tuleb ka ikka teha..
# 23.03.2013 dichannels reporting (on change and on renotify timeout) OK! execution (di reading) interval is about 3 loops per second, how to improve?
# 24.03.2013 remote update commands to be added. renamed to acomm_srv7.py. update using wget seemsm ok. subdirectories py and sql created. renamed to channelmonitor.py
# 04.04.2013 streamlining the flow, adding some exception handling. recovers from tcp conn problems (close/reopen socket for modbusproxy).
# 05.04.2013 exception length 9! udp message maximum length (limit 10?), delete the oldest from buff2server if no ack in i60 seconds? 
# 06.04.2013 DI bit values to 0/1, instead of  0/256 and so on
# 07.04.2013 usable for fair demo. aichannels update (appdelay) 10s instead of 120.

# PROBLEMS and TODO
# inserting to sent2server does not work for some reason. skipping it for now, no local log therefore.
# does not recover yet from ip address chg, results in udp comm loss. 
# separate ai reading and ai sending intervals!




# ### procedures ######################




def findmyip(): # ip address of the android host
    global host
    interfaces = android_network.NetworkInterface.getNetworkInterfaces()
    for interface in interfaces:
        if interface.isLoopback():
            continue
        addresses = interface.getInetAddresses()
        if addresses != None and len(addresses) > 0:
            for address in addresses:
                if isinstance(address, network.Inet4Address):
                    host = address.getHostAddress()
                    print 'android own ip',host
                    sys.stdout.flush()
                    time.sleep(2)
                    return
    raise Exception('Valid host not found')

    
    
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
    

    
def channelconfig(): # channel setup register setting based on devicetype and channel registers configuration. try to check channel conflicts
    global tcperr # not yet used, add handling
    respcode=read_register(1,1,1) # test connection
    if respcode>0:
        print "no modbusproxy connection?"
        sys.stdout.flush()
        time.sleep(1)
        return 1
    else:    
        write_register(1,271,0,0) # ana port as ai inputs. mba=1, reg=275, data 0. coilmode 0.
        write_register(1,275,0,0) # ana port direction, 0=input. coilmode 0.
        write_register(1,276,30,0) # usbreset protection 30 s from reboot before counting rs485 timeout
        write_register(1,277,1310,0) # usb reset in 30 s for 5s
        write_register(1,278,30,0) # button protection 30 s from reboot before counting rs485 timeout
        write_register(1,279,1400,0) # button pulse in 120 s for 5s. hex 0578
        # add here channels configuration based logic to set control registers.
        return 0



def modbus_comm(sdata): # send and receive to/from modbus devices
    global tcpaddr, tcpport, response, tcpmode
    
    loccount=1 # by default 1 register to read
    locmba=ord(sdata[tcpmode*6]) # modbus address
    locfunction=ord(sdata[1+tcpmode*6]) # command to use
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
        print 'failed sending read request to',tcpaddr, tcpport # need to restart the socket
        #traceback.print_exc()
        return 2 # restart socket
     

    if ready[0]: # midagi on tulnud
        response = tcpsocket.recv(1024) # kuulame
        msg="<== "+tcpaddr+":"+str(tcpport)+" "+response.encode('hex')
        #print msg,  # debug, no line feed
        if len(response) == ExpExc: # likely exception 
            retfunction=ord(response[1+tcpmode*6])
            #if retfunction <> locfunction: # the same as sent
            if (retfunction&128): # error bit raised in response function code
                retexception=ord(response[2+tcpmode*6])
                #print 'modbus_comm() locfunction, retfunction,retexception',format("%02x" % locfunction), format("%02x" % retfunction), format("%02x" % retexception) #debug
                #print 'exception source is the device with mba',locmba,'illegal command or address'
                    
                if retexception == 10: # 0A hex, gw problem
                    print 'modbusERR10: gw - RS485 unreachable'
                    return 1

                if retexception == 11: # 0B hex, device unreachable
                    print 'modbusERR11: no response from mba',locmba
                    #print('!'+str(locmba)), # less talk with that common error
                    return 1
                
                if retexception == 4: # 04 hex, device failure, could be crc error
                    print 'modbusERR4: crc error from mba',locmba
                    return 1

                    
        if locfunction == 3: # register(s) read
            if len(response) <> ExpLen: # not a valid response, while for barionet reg count can be negative!
                # counter read response example: 15010000000700030477c80001
                print 'modbusERR: read failure - illegal response length of',len(response),'instead of',3+abs(loccount)*2+tcpmode*6
                return 1 # back to parent
        else: # register write
            if sdata <> response[:len(sdata)]: # response is different from expected
                print 'modbusERR: write failure - illegal response content or length'
                return 1 # back to parent
                
    else: # no data from modbusproxy
        print 'modbusERR: no answer in 1.5s on request from',tcpaddr,tcpport # debug
        return 3 # bigger problem, modbusproxy MUST response
    
    #time.sleep(0.05) # to prevent sending immediate next request
    return 0



def read_register(locmba,locreg,loccount): # read via modbustcp, params mba,register address to start from,register count.
# the result form multiple registers will be joined into one value, 32 bits or more
    #local locmba,locreg,loccount
    global tcpport, tcpaddr, tcpdata, tcpmode, tcpwait  # tcpmode 0 or 1, controls header presence to the proxy and the expected response length
    hexstring=""
    mbah=format("%02x" % locmba) # mbah=mba.encode('hex') # hex kujul mba
    regaddrh=format("%04x" % locreg) # regaddr=reg.encode('hex') # hex kujul reg addr (reg nr on see+1!)
    regcounth=format("%04x" % abs(loccount)) # reg arv hex, abs vaartus sest negatiivne ei tohi olla!
    
    if tcpmode == 1: # add header
        hexstring="150100000006"
    
    hexstring=hexstring+mbah+"03"+regaddrh+regcounth
    
    try:
        sdata=hexstring.decode('hex') #binary string, not hex
    except:
        print 'invalid hexstring in read_register()',hexstring

    tcpdata=0 # vastus esialgu 0
    tcpessa=0 # esialgu, local
    
    respcode=modbus_comm(sdata) # returns binary string from modbus   ################################## modbus communication to read ################################
        
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
                    
            if loccount == 2: # normaalne loendi kus registrite jarjekooras MSW LSW
                if lenn == 4:  # 2 baidine vastus ehk 32 bitti
                    tcpdata=tcpdata+656636*tcpessa # 4-baidiseks vaartuseks, margita
                    #tcpdata=tcpdata|(tcpessa<<16) # 4-baidiseks vaartuseks, margita
                    #print 'normal counter',locreg,'first came MSW',tcpessa,'hex',format("%04x" % tcpessa),', total',tcpdata,'hex',format("%08x" % tcpdata) # ajutine                   
                    
            
        else:
            print 'invalid response length',lenn,'for result',tcpdatah
            return 1
            
    else: # respcode not 0
        return respcode
           
    return 0
# end read_register()

    
def write_register(mba,reg,wdata,coilmode): # writing one coil (mode=1) or 16-bit register (mode=0), 
    global tcpport, tcpaddr, tcpwait, tcpmode, lastreg 
    mbah=format("%02x" % mba) # mbah=mba.encode('hex') # hex kujul mba
    regaddrh=format("%04x" % reg) # regaddr=reg.encode('hex') # hex kujul reg addr (reg nr on see+1!)
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
    
    sdata=hexstring.decode('hex') #binaarseks stringiks, mitte hex
    numm=0 # tulemus numbrina # hiljem selle asemel array

    respcode=modbus_comm(sdata) # returns binary string from modbus   ################################## modbus communication to write ################################
    return respcode
   
# WRITE_REGISTER() END




def write_dochannels():
    # find out which do channels need to be changed based on dichannels and dochannels value differencies
    # and use write_register() write modbus registers (not coils) to get the desired result (all do channels must be also defined as di channels in dichannels table!)
    global inumm,ts,ts_inumm,mac,tcpdata,tcperr
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
        # ##try:
        cursor3.execute(Cmd3)
        #conn3.commit()
        
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
            if respcode == 0: # coil writing, gets converted to ff00 if value =1
                tcperr=0
                
            else:
                tcperr=tcperr+1 # increase error count
                if respcode ==2:
                    print 'problem with coil',mba,regadd,value,'writing!'
                
        #conn3.commit()  # dicannel-bits transaction end

    except:
        print 'problem with dochannel grp select!'
        sys.stdout.flush()
        #time.sleep(1)
        #traceback.print_exc()
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
                    if respcode == 2: # register writing, gets converted to ff00 if value =1
                        socket_restart() # close and open tcpsocket
                        
            
        #conn3.commit()  # dicannel-bits transaction end

    except:
        print 'problem with dichannel grp select in write_do_channels!'
        sys.stdout.flush()
        #time.sleep(1)
        #traceback.print_exc()
    
    
    conn3.commit() # transaction end
    
# write_dochannels() end. FRESHENED DICHANNELS TABLE VALUES AND CGH BITS (0 TO SEND, 1 TO PROCESS)



    

def read_aichannels(): # analogue inputs via modbusTCP, to be executed regularly (about 1..3 s interval). send to server once in 1..3 minute
    locstring="" # local
    global inumm,ts,ts_inumm,mac,tcpdata, tcperr
    mba=0 # lokaalne siin
    val_reg=''
    desc=''
    comment=''
    mcount=0
    block=0 # vigade arv
    ts_created=ts # selle loeme teenuse ajamargiks
    
    try:
        Cmd3="BEGIN IMMEDIATE TRANSACTION" # conn3, kogu selle teenustegrupiga (aichannels) tegelemine on transaction
        conn3.execute(Cmd3)
        
        Cmd3="select val_reg,count(member) from aichannels group by val_reg"
        #print "Cmd3=",Cmd3
        # #try:
        cursor3.execute(Cmd3)
        Cmd1="BEGIN IMMEDIATE TRANSACTION" # conn3, kogu selle teenustegrupiga (aichannels) tegelemine on transaction
        conn1.execute(Cmd1) # buff2server
    
        for row in cursor3: # teenuse seest teenuse liikmete formeerimise info lugemine, tuleb mitu rida
            lisa='' # vaartuste joru
            val_reg=''  
            sta_reg=''
            status=0 # esialgu

            val_reg=row[0] # teenuse nimi
            mcount=int(row[1])
            sta_reg=val_reg[:-1]+"S" # nimi ilma viimase symbolita ja S - statuse teenuse nimi, analoogsuuruste ja temp kohta
            svc_name='' # mottetu komment puhvri reale?
            #print 'reading aichannels values for val_reg',val_reg,'with',mcount,'members' # ajutine
            Cmd3="select * from aichannels where val_reg='"+val_reg+"'" # loeme yhe teenuse kogu info
            #print Cmd3 # ajutine
            
            try:
                cursor3a.execute(Cmd3) # teine kursor sama tabeli lugemiseks
                ##conn3.commit()
                for srow in cursor3a: # ridu nii palju kui teenuse liikmeid, pole oluline kuidas mba ja regadd vahele jaotatud
                    #print srow # ajutine
                    mba=0 # lokaalne siin
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
                    #tvalue=0 # test, vordlus
                    oraw=0
                    ovalue=0 # eelmine voi keskmistatud, mida ise tagasi kirjutad. app kasutabki seda!
                    ots=0 # eelmine ts value ja status ja raw oma
                    avg=0 # keskmistamistegur, mojub alates 2
                    desc=''
                    comment=''
                    # 0       1     2     3     4   5  6  7  8  9    10     11  12    13  14   15     16  17    18
                    #mba,regadd,val_reg,member,cfg,x1,x2,y1,y2,outlo,outhi,avg,block,raw,value,status,ts,desc,comment  # aichannels
                    if srow[0]<>'':
                        mba=int(srow[0])
                    regadd=int(srow[1]) # igaks juhuks numbriks
                    val_reg=srow[2] # see on string
                    if srow[3]<>'':
                        member=int(srow[3])
                    if srow[4]<>'':
                        cfg=int(srow[4]) # konfibait nii ind kui grp korraga, esita hex kujul hiljem
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
                        avg=int(srow[11])  #  keskmistamise tugevus, vaartused 0 ja 1 ei keskmista!
                    if srow[12]<>'': # block - loendame siin vigu, kui kasvab yle 3? siis enam ei saada
                        block=int(srow[12])  #  
                    if srow[13]<>'': # 
                        oraw=int(srow[13])
                    if srow[14]<>'': # siit alates muuda aichannels tabeli sruktuuri!!
                        ovalue=int(srow[14])
                    if srow[15]<>'':
                        ostatus=int(srow[15])
                    if srow[16]<>'':
                        ots=int(srow[16])
                    desc=srow[17]
                    comment=srow[18]
    
                
                    if mba>=0 and mba<256 and regadd>=0 and regadd<65536:  # usutav mba ja regaddr
                        print 'reading mba',mba,'regadd',regadd,'for val_reg',val_reg,'member',member,  # ajutine
                        
                        respcode=read_register(mba,regadd,1)
                        if respcode == 0: # got  tcpdata as register content. convert to scale.
                            #print 'value',tcpdata
                            tcperr=0
                            if lisa<>"":
                                lisa=lisa+" "
                                
                            if x1<>x2 and y1<>y2: # sisendandmed usutavad
                                value=(tcpdata-x1)*(y2-y1)/(x2-x1)
                                value=y1+value 
                                
                                print 'aichannels raw',tcpdata,', converted value',value,', ovalue',ovalue,', avg',avg, # siia taha tuleb veel jargmine print samale reale
                                if avg>1 and abs(value-ovalue)<value/2: # keskmistame, hype ei ole suur
                                #if avg>1:  # lugemite keskmistamine vajalik, kusjures vaartuse voib ju ka komaga sailitada!
                                    value=((avg-1)*ovalue+value)/avg # averaging
                                    print ', averaged value',value
                                else: # no averaging for big jumps
                                    if tcpdata == 4096: # this is error result from 12 bit 1wire temperature sensor
                                        value=ovalue # repeat the previous value. should count the errors to raise alarm in the end! counted error result is block, value 3 stps sending. 
                                    else: # acceptable non-averaged value
                                        print ', no averaging, value jump to',value
                                    
                                
                               
                                # check the value limits and set the status, acoording to configuration byte cfg bits values
                                # use hysteresis to return from non-zero status values
                                if value>outhi: # above hi limit
                                    if (cfg&4) == 4 and status == 0: # warning 
                                        status=1
                                    if (cfg&8) == 8 and status<2: # critical 
                                        status=2
                                    if (cfg&12) == 12: #  not to be sent
                                        status=3
                                        block=block+1 # error count incr
                                else: # retrn with hysteresis 5%
                                    if value>outlo and value<outhi-0.05*(outhi-outlo): # value must not be below lo limit in order for status to become normal
                                        status=0 # back to normal
                                        block=0 # reset error counter
                                
                                if value<outlo: # below lo limit
                                    if (cfg&3) == 1 and status == 0: # warning
                                        status=1
                                    if (cfg&3) == 2 and status<2: # critical
                                        status=2
                                    if (cfg&3) == 3: # not to be sent
                                        status=3
                                        block=block+1 # error count incr
                                else: # back with hysteresis 5%
                                    if value<outhi and value>outlo+0.05*(outhi-outlo):
                                        status=0 # back to normal
                                        block=0
                                        
                               
                                
                                #aichannels update with new value and sdatus
                                Cmd3="UPDATE aichannels set status='"+str(status)+"', value='"+str(value)+"', ts='"+str(int(ts))+"' where val_reg='"+val_reg+"' and member='"+str(member)+"'" # meelde
                                #print Cmd3 
                                try:
                                    conn3.execute(Cmd3) # kirjutamine
                                    ##conn3.commit() # tegelik kirjutamine
                                except:
                                    print 'problem with aichannels update!'
                                    #traceback.print_exc()
                                        
                            
                            
                            else:
                                print "val_reg",val_reg,"member",member,"ai2scale PARAMETERS INVALID:",x1,x2,'->',y1,y2,'value not used!'
                                value=0 
                                status=3 # not to be sent status=3! or send member as NaN? 
                            

                            lisa=lisa+str(value) # adding member values into one string

                        else: # failed reading register
                            tcperr=tcperr+1 # increase error counter
                            print 'failed to read ai register', mba,regadd
                            if resp_code == 2:
                                socket_restart() # close and open tcpsocket
                                #conn3.commit() # aichannels transaction end
                                return 1
                        
                            
                    else:
                        print 'invalid mba / regadd',mba,'/',regadd 
                        #conn3.commit() # aichannels transaction end
                        return 1
                
                # service data existing, put into buffer table
                if block<blocklimit: # can be sent
                    try:
                        #print mac,host,port,svc_name,sta_reg,status,val_reg,lisa,ts_created,inumm # ajutine
                        Cmd1="INSERT into buff2server values('"+mac+"','"+host+"','"+str(port)+"','"+svc_name+"','"+sta_reg+"','"+str(status)+"','"+val_reg+"','"+str(lisa)+"','"+str(int(ts_created))+"','','')" 
                        #print "ai Cmd1=",Cmd1 # debug
                        conn1.execute(Cmd1) # write aichannels data into buff2server
     
                    except:
                        print 'problem with',Cmd1
                        sys.stdout.flush()
                        #time.sleep(1)
                        #traceback.print_exc() 
                else:
                    print 'cannot send service',svc_name,'error, block=',block
                  
        
            except:
                print 'could not read data for val_reg',val_reg
                #traceback.print_exc()
                
        #conn3.commit() # aichannels transaction end
        
        Cmd1="select count(mac) from buff2server" # debug test
        cursor1.execute(Cmd1) # debug test
        for row in cursor1: # debug test
            print row[0],'rows in buff2server after aichannels processing' # debug test
            
        conn1.commit() # buff2server transaction end
            
    except:
        print 'problem with aichannels reading'
        sys.stdout.flush()
        #time.sleep(1)
        #traceback.print_exc()
    
    conn3.commit()

#read_aichannels end

    

    

def read_dichannel_bits(): # binary inputs, changes to be found
# reads 16 bits as di or do channels to be reported to monitoring
# NB the same bits can be of different rows, to be reported in different services. services and their members must be unique
    locstring="" # see on siin lokaalne!
    global inumm,ts,ts_inumm,mac,tcpdata, tcperr
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
    
    #Cmd3="BEGIN IMMEDIATE TRANSACTION" # conn3, kogu selle teenustegrupiga (aichannels) tegelemine on transaction
    #conn3.execute(Cmd3) # ei tee yhte suurt trans?
    
    Cmd3="select mba,regadd from dichannels group by mba,regadd" # saame registrid mida lugeda vaja, mba ja regadd
    # loeme igat registrit ainult yks kord, sest bitid saame ju korraga katte (16tk)
    #print "Cmd3=",Cmd3
    #try:
    cursor3.execute(Cmd3)
    conn3.commit() # "" still lockesds, trying
    
    for row in cursor3: # teenuse seest teenuse liikmete formeerimise info lugemine, tuleb mitu rida
        regadd=0
        mba=0

        if row[0]<>'':
            mba=int(row[0]) # must ne number
        if row[1]<>'':
            regadd=int(row[1]) # must ne number
        #mcount=int(row[1])
        sta_reg=val_reg[:-1]+"S" # S as last char in service name for status transmission
        svc_name='' # unused?
        #print 'reading dichannel register mba,regadd',mba,regadd, # temporary
        
        Cmd3="BEGIN IMMEDIATE TRANSACTION" # conn3, proovin transactioni registrite kaupa
        try:
            conn3.execute(Cmd3) # ei tee yhte suurt trans?
        except:
            conn3.commit() # proovin
            print 'trans begin problem, commit and return from read_dichannel_bits()'
            sys.stdout.flush()
            #time.sleep(1)
            return 1 # conn3.execute(Cmd3) # ei tee yhte suurt trans?
            
        Cmd3="select bit,value from dichannels where mba='"+str(mba)+"' and regadd='"+str(regadd)+"' group by regadd,bit" # loeme koik di kasutusel bitid sellelt registrilt
        #  every bit will have it's own row in buffer table!
        #print Cmd4 # temporary
        
        #try:
        cursor3a.execute(Cmd3)
        # # conn3.commit() # ?? without that database locked on di bit change!
        
        respcode=read_register(mba,regadd,1)
        if respcode == 0: # successful DI register reading - continuous to catch changes! ################################
            tcperr=0
            #print 'got di word',format("%02x" % tcpdata) # tcpdata.encode('hex') # hex kujul 16 bitti
            
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
                
                #kontrollime muutmisi ja salvestame uued vaartused tabelisse ning maskmuutujasse ichg
                if value <> ovalue: # change detected, update dichannels value, chg-flag
                    chg=3 # 2-bit change flag, bit 0 to send and bit 1 to process, to be reset separately
                    #ichg=ichg+2**bit # adding up into the change mask
                    print 'DIchannels',mba,regadd,'bit',bit,'change! was ',ovalue,', became',value # temporary
                    
                    # dichannels table update with new bit values and change flags. no status change here. no update if not changed!
                    Cmd3="UPDATE dichannels set value='"+str(value)+"', chg='"+str(chg)+"', ts_chg='"+str(int(ts))+"' where mba='"+str(mba)+"' and regadd='"+str(regadd)+"' and bit='"+str(bit)+"'" # uus bit value ja chg lipp, 2 BITTI!
                    #print Cmd3 # temporary
                    try:
                        conn3.execute(Cmd3) # write
                        # #conn3.commit() # ?? tegelik kirjutamine
                    except:
                        print 'problem with',Cmd3
                        sys.stdout.flush()
                        #time.sleep(1)
                        #traceback.print_exc() 
                
        else:
            tcperr=tcperr+1 # increase error counter
            #print 'failed to read di register from mba,regadd', mba,regadd
            print regadd, # common problem, keep it shorter
            if respcode == 2:
                socket_restart() # close and open tcpsocket
                return 2
        
        conn3.commit()  # dichannel- service transaction end
        
    conn3.commit()  # dichannel-bits transaction end / NOT USED?

    

# read_dichannel_bits() end. FRESHENED DICHANNELS TABLE VALUES AND CGH BITS (0 TO SEND, 1 TO PROCESS)






def make_dichannel_svc(): # di services into to-be-sent buffer table BUT only when member(s) changed or there is a need for renotification
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
        conn3.execute(Cmd3)
        
        Cmd3="select val_reg,max((chg+0) & 1),min(ts_msg+0) from dichannels where ((chg+0 & 1) and ((cfg+0) & 16)) or ("+str(int(ts))+">ts_msg+"+str(renotifydelay)+") group by val_reg"  
        # take into account cfg! not all changes are to be reported immediately! cfg is also for application needs, not only monitoring!
        # #try:
        cursor3.execute(Cmd3)
        conn3.commit() # ?? locked vastu
        
        for row in cursor3: # services to be processed. either just changed or to be resent
            lisa='' # stringx of space separated values
            val_reg=''  
            sta_reg=''
            status=0 # at first

            val_reg=row[0] # service name
            chg=int(row[1]) # change bitflag here, 0 or 1
            ts_last=int(row[2]) # last reporting time
            if chg == 1: # message due to bichannel state change
                print 'DI service to be reported due to change:',val_reg,'while last reporting was',ts-ts_last,'s ago, ts now=',ts
            else:
                print 'DI service',val_reg,'no state change, but to be REreported, last reporting was',ts-ts_last,'s ago, ts now=',ts
                
            #mcount=int(row[1]) # changed service member count
            sta_reg=val_reg[:-1]+"S" # service status register name
            svc_name='' # unused? but must exist for insertion int obuff2server
            #print 'reading dichannels values for val_reg',val_reg,'with',mcount,'changed members' # debug if then member number is low, then change was the reason. 
            # otherwise renotification (if chaged member count is equalt to total member count).
            Cmd3="select * from dichannels where val_reg='"+val_reg+"' order by member asc" # data for one service ###########
            #print Cmd3 # temporary
            try:
                cursor3a.execute(Cmd3)
            
                for srow in cursor3a: # ridu tuleb nii palju kui selle teenuse liikmeid, pole oluline milliste mba ja readd vahele jaotatud
                    #print srow # temporary
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
                    regadd=int(srow[1]) # must be number
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

                
                    #print 'DI for bit',bit,'in val_reg',val_reg,'member',member,'value',value  # temporary
                   
                    if lisa<>"":
                        lisa=lisa+" "
                        
                     
                       
                    # status and inversions according to configuration byte
                    if (cfg&1) == 1: # status warning if value 1
                        status=value # 
                    if (cfg&2) == 2: # status critical if value 1
                        status=2*value 
                    if (cfg&4) == 4: # status inversion
                        status=(1^status) 
                    if (cfg&8) == 8: # value inversion xor abil, TODO enne kui status TODOkse
                        value=(1^value) # possible member values 0 voi 1
                    if status>sumstatus:
                        sumstatus>status # suurem jaab kehtima
                    
                    
                    #dichannels table update with new chg ja status values. no changes for values! chg bit 0 off! set ts_msg!
                    Cmd3="UPDATE dichannels set status='"+str(status)+"', ts_msg='"+str(int(ts))+"', chg='"+str(chg&2)+"' where val_reg='"+val_reg+"' and member='"+str(member)+"'" 
                    # bit0 from change flag stripped! this is to notify that this service is sent (due to change). may need other processing however.
                    #print Cmd3 # di reporting debug
                    try:
                        conn3.execute(Cmd3) # kirjutamine
                        conn3.commit() # tegelik kirjutamine ?? locked vastu
                    except:
                        print 'problem with',Cmd3
                        sys.stdout.flush()
                        #time.sleep(1)
                        #traceback.print_exc() 
                        
                            
                    

                        
                    lisa=lisa+str(value) # adding member to multivalue string
                    
                    
                # sending service data into buffer table when the loop above is finished
                try:
                    #print mac,host,port,svc_name,sta_reg,status,val_reg,lisa,ts_created,inumm # temporary
                    Cmd1="INSERT into buff2server values('"+mac+"','"+host+"','"+str(port)+"','"+svc_name+"','"+sta_reg+"','"+str(status)+"','"+val_reg+"','"+str(lisa)+"','"+str(int(ts_created))+"','','')" 
                    #print "di Cmd1=",Cmd1 # debug
                    conn1.execute(Cmd1) # kirjutamine
 
                except:
                    print 'problem with',Cmd1
                    sys.stdout.flush()
                    #time.sleep(1)
                    #traceback.print_exc() 
                        
                    
            except:
                print 'could not read dichannels data for val_reg',val_reg
                sys.stdout.flush()
                #time.sleep(1)
                #traceback.print_exc()
                  
        
        conn1.commit() # buff2server
        conn3.commit() # dichannels transaction end / VEEL KORD?
            
    except: 
        print 'problem with reading dichannels'
        sys.stdout.flush()
        #time.sleep(1)
        #traceback.print_exc()
        
#make_dichannel_svc() lopp





    
def read_counters(): # counters, usually 32 bit / 2 registers.
    locstring="" # see on siin lokaalne!
    global inumm,ts,ts_inumm,mac,tcpdata,tcperr
    mba=0 # lokaalne siin
    val_reg=''
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
        #try:
        cursor3.execute(Cmd3)
        ##conn3.commit()
        
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
            
            try:
                cursor3a.execute(Cmd3)
                ##conn3.commit()
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
                        mba=int(srow[0])
                    regadd=int(srow[1]) # must be number
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
                            if (cfg&16) == 16: # power, increment to be calculated! divide increment to time from the last reading to get the power
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
                            if value>outhi: # yle ylemise piiri
                                if (cfg&4) == 4 and status == 0: # warning if above the limit
                                    status=1
                                if (cfg&8) == 8 and status<2: # critical if  above the limit
                                    status=2
                                if (cfg&12) == 12: # unknown if  above the limit
                                    status=3
                            else: # return to normal with hysteresis
                                if value<outhi-0.05*(outhi-outlo):
                                    status=0 # normal again
                            
                            if value<outlo: # below lo limit
                                if (cfg&3) == 1 and status == 0: # warning if below lo limit
                                    status=1
                                if (cfg&3) == 2 and status<2: # warning  if below lo limit
                                    status=2
                                if (cfg&3) == 3: # unknown  if below lo limit
                                    status=3
                            else: # return
                                if value>outlo+0.05*(outhi-outlo):
                                    status=0 # normal again
                                    
                                    
                           
                            
                            #counters table update
                            Cmd3="UPDATE counters set status='"+str(status)+"', value='"+str(value)+"', raw='"+str(raw)+"', ts='"+str(int(ts))+"' where val_reg='"+val_reg+"' and member='"+str(member)+"'" 
                            #print Cmd3 # temporary
                            try:
                                conn3.execute(Cmd3) # update counters
                                ##conn3.commit() # tegelik kirjutamine
                            except:
                                print 'problem with',Cmd3
                                sys.stdout.flush()
                                #time.sleep(1)
                                #traceback.print_exc() 
                                                    
                            lisa=lisa+str(value) # members together into one string
                            
                        else: # register read failed
                            tcperr=tcperr+1
                            print 'failed reading counter register',mba,regadd
                            if respcode == 2:
                                socket_restart()
                                
                    else:
                        print 'invalid mba / regadd',mba,'/',regadd 
                
                
                # sending in to buffer 
                #print mac,host,port,svc_name,sta_reg,status,val_reg,lisa,ts_created,inumm # temporary
                Cmd1="INSERT into buff2server values('"+mac+"','"+host+"','"+str(port)+"','"+svc_name+"','"+sta_reg+"','"+str(status)+"','"+val_reg+"','"+str(lisa)+"','"+str(int(ts_created))+"','','')" 
                # inum and ts_tried empty a t first!
                #print "cnt Cmd1=",Cmd1 # debug
                try:
                    conn1.execute(Cmd1)
                    ##conn1.commit() # teenus tehtud ja puhvrisse pandud saatmist ootama
                    
                except:
                    print 'problem with',Cmd1
                    sys.stdout.flush()
                    #time.sleep(1)
                    #traceback.print_exc() 
                    
                  
        
            except:
                print 'problem with counters read 1'
                sys.stdout.flush()
                #time.sleep(1)
                #traceback.print_exc()
                
        conn3.commit() # counters transaction end
        conn1.commit() # buff2server transaction end
            
    except: # end reading counters
        print 'problem with counters read 2'
        sys.stdout.flush()
        #time.sleep(1)
        #traceback.print_exc() 
        
#read_counters end #############
 
 
        
    

def report_setup(): # send setup data to server via buff2server table as usual
    locstring="" # local
    global inumm,ts,ts_inumm,mac,host,port,TODO # 
    mba=0 # lokaalne siin
    reg=''
    reg_val=''
    Cmd1=''
    Cmd4='' 
    ts_created=ts
    svc_name='setup value'
    
    try:
        Cmd4="BEGIN IMMEDIATE TRANSACTION" # conn4 asetup
        conn4.execute(Cmd4)
        Cmd1="BEGIN IMMEDIATE TRANSACTION" # conn1 buff2server
        conn1.execute(Cmd1)
        
        Cmd4="select register,value from asetup" # no multimember registers for setup!
        print Cmd4 # temporary
    
        # # try:
        cursor4.execute(Cmd4)
        
        for row in cursor4: # 
            val_reg=''  # string
            reg_val=''  # string
            status=0 # esialgu
            #value=0

            val_reg=row[0] # muutuja  nimi
            reg_val=row[1] # string even if number!
                
            # sending to buffer, no status counterparts! status=''
            Cmd1="INSERT into buff2server values('"+mac+"','"+host+"','"+str(port)+"','"+svc_name+"','','','"+val_reg+"','"+reg_val+"','"+str(int(ts_created))+"','','')" 
            # panime puhvertabelisse vastuse ootamiseks. inum ja ts+_tried esialgu tyhi! ja svc_name on reserviks! babup vms... # statust ei kasuta!!
            print "stp Cmd1=",Cmd1 # temporary debug
            try:
                conn1.execute(Cmd1)
                ##conn1.commit() # teenus tehtud ja puhvrisse pandud saatmist ootama
                
            except:
                print 'problem with',Cmd1
                sys.stdout.flush()
                #time.sleep(1)
                #traceback.print_exc()
            
              
        
        conn1.commit() # buff2server trans lopp
        conn4.commit() # asetup trans lopp
            
    except: # teenuste lugemine
        print 'problem with setup reading',Cmd4
        sys.stdout.flush()
        time.sleep(1) # setup
        #traceback.print_exc()
        
#report_setup lopp#############
    
 
 
 
 
   
def unsent():  # delete unsent for too long messages - kas seda ikka on vaja?
    global ts,renotifydelay
    Cmd1="BEGIN IMMEDIATE TRANSACTION"  # buff2server
    conn1.execute(Cmd1)
    Cmd1="SELECT inum,svc_name,sta_reg,status,val_reg,value,ts_created,ts_tried from buff2server where ts_created+0<"+str(ts+2*renotifydelay) # yle 2x regular notif
    print Cmd1 # korjab ka uued sisse!
    cursor1.execute(Cmd1)
    #conn1.commit()
    for rida in cursor1:
        print '!! unsent for',3*renotifydelay,'sec, to be deleted:',repr(rida)
        
    Cmd1="delete from buff2server where ts_created+0<"+str(ts+3*renotifydelay)
    conn1.execute(Cmd1)
    conn1.commit() # buff2server transaction end
        
#unsent() end    
 

 
def udpmessage(): # udp message creation based on  buff2server data, does the retransmits too if needed. 
    # buff2server rows will be deleted and inserted into sent2buffer table based on in: contained in ack message 
    # what happens in case of connectivity loss?
    # inumm on global in: to be sent, inum on global in: to be received in ack
    # 16.03.2013 switching off saving to sent2server! does not work and not really needed! logcat usable as replacement.
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
    
    Cmd1="DELETE * from buff2server where ts_created+60<"+str(int(ts)) # deleting too old unsent stuff, not deleted by received ack
    conn1.execute(Cmd)
    # instead of or before deleting the records could be moved to unsent2server table (not existing yet). dumped from there, to be sent later as gzipped sql file
    
    Cmd1="SELECT * from buff2server where ts_tried='' or (ts_tried+0>1358756016 and ts_tried+0<"+str(timetoretry)+") order by ts_created asc"  # +0 to make it number! use no limit!
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
            try:
                conn1.execute(Cmd1)
            except:  #
                print 'problem with',Cmd1
                sys.stdout.flush()
                #time.sleep(1)
                #traceback.print_exc()
                
        if svc_count>0: # there is something (changed services) to be sent!
            print svc_count,"services using inumm",inumm,"to be sent now, at",ts
            udpsend(inumm,int(ts)) # sending away inside udpmessage()
        
        Cmd1="SELECT count(mac) from buff2server"  # unsent row (svc member) count in buffer
        cursor1.execute(Cmd1) # 
        for srow in cursor1:
            svc_count2=int(srow[0]) # total number of unsent messages
            
        if svc_count2>0:
            print svc_count2,"SERVICE LINES IN BUFFER waiting for ack from monitoring server"
 
    except: # buff2server reading unsuccessful. unlikely...
        print 'problem with buff2serverr read'
        sys.stdout.flush()
        #time.sleep(1)
        #traceback.print_exc()

        
    conn1.commit() # buff2server transaction end   

# udpmessage() end
##################    
    
   


    
def udpsend(locnum,locts): # actual udp sending, adding ts to in: for some debugging reason. if locnum==0, then no in: will be sent
    global sendstring,mac
    if sendstring == '': # nothing to send
        print 'sendtring: nothing to send!'
        return 1
        
    sendstring="id:"+mac+"\n"+sendstring # loodame, et ts_created on enam-vahem yhine neil teenustel...
    if locnum >0: # in: to be added
        sendstring="in:"+str(locnum)+","+str(locts)+"\n"+sendstring
    try:
        UDPSock.sendto(sendstring,saddr)  
        sendlen=len(sendstring)
        #print "sent len",sendlen,"with in:"+str(locnum),sendstring[:66],"..." #sendstring
        print "sent",sendstring.replace('\n',' ')   # show as one line
        #syslog.syslog('=> '+sendstring.replace('\n',' ')) # syslog line (only sent)
        logging.debug("sending"+sendstring) # trying to use logcat to catch it
        sendstring=""
    except:
        print "udp send failure for udpmessage!"
        #traceback.print_exc() # no success for sending
 

def update(todo): # par string, int. download a file from support server (global)
    global SUPPORTHOST
    filename=todo.split(',')[1]
    try:
        filesize=int(TODO.split(',')[2])
    except:
        print 'update failed due to invalid filesize'
        return 1
        
    if filename<>'' and filesize>0: # parameters seem valid
        if subexec('wget '+SUPPORTHOST+filename,0) == 0: # success
            try:
                dnsize=os.stat(filename)[6]  # int(float(subexec('ls -l '+filename,1).split(' ')[4]))
            except:
                print 'update: could not get filesize for downloaded',filename
                
            if dnsize == filesize: # ok
                print 'downloaded file size OK on first try',dnsize
                
                
        else: #try again - once for now, add loops later
            if subexec('wget -c '+SUPPORTHOST+filename,0) == 0:
                print 'downloaded file size ok on second try',filesize
                try:
                    dnsize=s.stat(filename)[6] # int(float(subexec('ls -l '+filename,1).split(' ')[4]))
                except:
                    print 'update: could not get filesize for downloaded',filename
                
                if dnsize == filesize: # ok
                    print 'downloaded file size OK on second try',dnsize
                    
            else:
                print 'download failed, ls -l: ',repr(subexec('ls -l '+filename))
                return 1
                
        if unpack(todo) == 0:
            print filename,'unpack successful'
            return 0
        else:
            print filename,'unpack failed for some reason!'
            return 2
                    
#aga jargmised voiks toimuda ka koik iseenesest update sees, kui download onnestub!

def unpack(todo): # par string, unpack tgz. the same todo as for update should do as well!
    filename=todo.split(',')[1]
    filelist=subexec('tar -ztf '+filename,1) # files to be reloaded later
    filedir=filelist.splitlines()[0] # directory for the unpacked files. not needed as path is incl;uded with every filename
    files=filelist.splitlines()[1:] # array of the files, assuming the directory was on the first line
    if subexec('tar -xzf '+filename,0)>0: # returncode not 0
        print 'unpack: unpacking',filename,'failed, update interrupted'
        return 1
        
    print 'unpack:',filename,'unpacked, going to process'    
    #processing the unpacked files depending on the archive name, sql or py supported at this stage
    if filename == 'sql.tgz': # sqlite files to recreate tables
        print 'unpack: sql table update starting'
        for fnum in range(len(files)): # for each file in the archive
            filee= files[fnum].split('/')[1].split('.')[0] # tablename extracted
            print 'unpack: updating table',filee,', new content will be listed' 
            if len(filee)>5: # looks like normal tablename
                newfile=subexec('sql/reload_sql.sh '+filename,1) # no success with python .read, this is simpler!
                print newfile # resulting table content
                
               # refreshing sql files should be here, see dbcreate.py
               
    if filename == 'py.tgz': # python files to replace (possibly running) scripts
        print 'unpack: py scripts update starting'
        for fnum in range(len(files)): # for each file in the archive
            filee= files[fnum].split('/')[1].split('.')[0] # tablename extracted
            if len(filee)>5: # looks like normal scriptname
                subexec('ps1kill '+filename,0)    
    # all py files tables in archive killed            
    
    print 'unpack finished'
    
#def reload(todo): # par string, recreate sqlite tables given, wildcards usable
#def kill(todo): # par string, kills named script (to be restarted automatically if needed)



def socket_restart(): # close and open tcpsocket
    global tcpaddr, tcpport, tcpsocket
    
    try: # should be possible if exists
        print 'closing tcp socket'
        tcpsocket.close()
        time.sleep(2) 
        
    except:
        print 'problem closing tcp sopcket'
        #traceback.print_exc() # debug
        
    # open a new socket
    try:
        print 'opening tcp socket to modbusproxy,',tcpaddr, tcpport
        
        tcpsocket = socket(AF_INET,SOCK_STREAM) # tcp / must be reopened if pipe broken, no reusage
        tcpsocket.settimeout(5) #  conn timeout for modbusproxy. ready defines another (shorter) timeout after sending!
        tcpsocket.connect((tcpaddr, tcpport)) # leave it connected
        
    except:
        print 'modbusproxy socket open failed, to',tcpaddr, tcpport
        #traceback.print_exc() # debug
        sys.stdout.flush() # to see the print lines above in log
    
    time.sleep(3) 

        
        

def stderr(message): # for android only? from entry.py of mariusz
    #import sys # already imported
    sys.stderr.write('%s\n' % message)

    
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

from socket import *
import string

#import syslog # only for linux, not android (logcat forwarded to external syslog there)
import select
import urllib2
import gzip
import tarfile
import logging

host='' # own ip 
tcpmode=1 # if 0, then no tcpmodbus header needed. crc is never needed.
OSTYPE='' # linux or not?

try:
    OSTYPE=os.environ['OSTYPE'] #  == 'linux': # running on linux, not android
    host=str(subexec('ifconfig | grep "inet addr" | grep -v "127.0" | grep Bcast | cut -d":" -f2 | cut -d" " -f1',1)).rstrip() # no newline. 
    tcpport=502 # std modbusTCP port # set before
    tcpaddr="10.0.0.11" # ip to use for modbusTCP
    from sqlite3 import dbapi2 as sqlite3 # in linux
    os.chdir('/srv/scada/acomm/sql')
    #print os.getcwd()
    mac="010000000011" # id in a form of mac address   ### individual for each agent/controller! use wlan or ethernet mac as id
    print 'started on linux, host',host,'tcpdevice',tcpaddr,'using mac',mac
    
except: # android
    #import android # these 2 lines are in network_utils.py
    #droid = android.Android()
    
    from android_context import Context
    import os.path

    import android_network # android_network.py and android_utils.py must be present!
    #findmyip() # sets hos as wlan or grps/3g ip 
    #host='192.168.43.1' # temporary test, could not use the previous...
    
    mac="D05162F46069" # id in a form of mac address, individual for each agent/controller! use wlan or ethernet mac as id
    
    tcpport=10502 # modbusproxy
    tcpaddr="127.0.0.1" # localhost ip to use for modbusproxy
    import BeautifulSoup # ? 
    #import gdata.docs.service 
    import termios
    import sqlite3
    os.chdir('/sdcard/sl4a/scripts/d4c')
    #print os.getcwd()
    
print 'current dir',os.getcwd()
port=44445 # 
buf=1024 #
#addr = (host,port) # itself
shost="46.183.73.35" # listening server
sport=port # server port
saddr=(shost,sport) # mon server


SUPPORTHOST='http://www.itvilla.ee/support/pyapp/'+mac+'/' 
print "SERVER saddr",saddr,', MODBUSPROXY tcpaddr',tcpaddr,tcpport
#print 'SUPPORTHOST',SUPPORTHOST

logging.debug("channelmonitor starting")

sys.stdout.flush() # to see the print lines above in log
time.sleep(1) # start

tcpwait=1.5 # alla 0.8 ei tasu, see on proxy tout...  #0.3 # how long to wait for an answer from modbusTCP socket

appdelay=10 # 120 # 1s appmain execution interval, reporting all analogue values and counters. NOT DI channels!! DO NOT REPORT AI EVERY TIME!!!

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

# Create socket and bind to address



UDPSock = socket(AF_INET,SOCK_DGRAM)
UDPSock.settimeout(0.1) # (0.1) use 1 or more for testing # in () timeout to wait for data from server. defines alsomain loop interval / execution speed!!
# shortening of timeout above below 0.1s does not speed main loop execution delay any more, the bigger delays are in sqlite and modbus communication
if OSTYPE == 'linux': # running on linux
    addr = (host,port)
    UDPSock.bind(addr)
else: # android
    try:
        host='192.168.43.1' # phone as hotspot
        addr = (host,port) # itself
        UDPSock.bind(addr)
        print 'phone in hotspot mode'
    except:
        print 'phone not in hotspot mode'
        try:
            host='10.0.0.188' # phone connected to wlanaddr
            addr = (host,port) # itself
            UDPSock.bind(addr)
            print 'phone in wifi mode'
        except:
            print 'phone not in wifi mode either...'
sys.stdout.flush()
time.sleep(2)
        
#modbusTCP parameters and OPEN
#tcpsocket = socket(AF_INET,SOCK_STREAM) # tcp / must be reopened i pipe broken
#tcpsocket.settimeout(5) #  conn timeout for modbusproxy. ready defines another (shorter) timeout after sending!

socket_restart() # socket to modbusproxy, first open

#tcpport=502 # std modbusTCP port # set before
#tcpaddr="10.0.0.11" # ip to use for modbusTCP
#try:
#    tcpsocket.connect((tcpaddr, tcpport)) # leave it connected
#except:
#    print 'could not connect to',tcpaddr, tcpport # no success
#    traceback.print_exc()    
#    sys.stdout.flush()
#    time.sleep(3)

#create sqlite connections
try:
    conn1 = sqlite3.connect('./buff2server',2) # buffer data from modbus registers, unsent or to be resent
    conn3 = sqlite3.connect('./modbus_channels',2) # modbus register related tables / sometimes locked!!
    conn4 = sqlite3.connect('./asetup',2) # setup table, only for update, NO INSERT! 2 s timeout. timeout will cause exexution stop.
    
except:
    print 'sqlite connection problem'
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

#syslog.openlog(ident="acomm_srv",logoption=syslog.LOG_PID,facility=syslog.LOG_LOCAL0) #syslog kaivitus
#syslog.syslog('Starting...'+APVER)


ts=time.mktime(datetime.datetime.now().timetuple()) #sekundid praegu
ts_boot=int(ts) # startimise aeg, UPV jaoks

# delete unsent rows older than 60 s
Cmd1="DELETE from buff2server where ts_created+0<"+str(ts)+"-60" # kustutakse koik varem kui ninute tagasi loodud
conn1.execute(Cmd1)
Cmd1="SELECT count(sta_reg) from buff2server" # kustutakse koik varem kui ninute tagasi loodud
cursor1.execute(Cmd1)
conn1.commit()
for row in cursor1:
    print row[0],'svc records (created during last minute) in buffer during startup' 
time.sleep(1) # buff2server delete old if any

if OSTYPE<>'linux': # android with pic-based io
    if channelconfig() == 0:
        print 'modbus devices configured'
        # write device config - specific control registers (channel directions, pullups and so on) based on channel configuration needed
    else:
        tcperr=tcperr+1
        print 'failed device config attempt'
        sys.stdout.flush()
        time.sleep(2) # ostype
    
sendstring="AVV:OpenSuse/Android, "+APVER+"\nAVS:0\nUPV:0\nUPS:1\n"
udpsend(inumm,int(ts)) # version data # could be put into buff2server too...

print 'reporting setup'
report_setup() # sending to server on startup

 
# #############################################################
# #################### MAIN ###################################
# #############################################################

# listening replies from the server and sending messages to the server via UDP. 
# Received messages from server include at least data for id and possibly in (if sent by the probe)
# start from accommm directory so py and sql are subdirectories!

while 1:
    try: # if anything comes into buffer in 0.1s
        setup_change=0 # flag to detect possible setup changes
        data,addr = UDPSock.recvfrom(buf)
        ts=time.mktime(datetime.datetime.now().timetuple()) #seconds now
        #print "got message from addr ",addr," at ",ts,":",data.replace('\n', ' ') # showing datagram members received on one line, debug
        #syslog.syslog('<= '+data.replace('\n', ' ')) # also to syslog (communication with server only)
        
        MONTS=str(int(ts)) # as integer, without comma
        
        
        if (addr[1] < 1 or addr[1] > 65536):
            print "illegal source port",addr[1],"in the message received from",addr[0]

        if addr[0] <> shost:
            print "illegal sender " + str(addr[0]) + " of message: " + data

        if "id:" in data: # mac aadress
            id=data[data.find("id:")+3:].splitlines()[0]
            if id<>mac:
                print "invalid id in server message from ", addr[0]
        
            Cmd1="" 
            Cmd2=""

            if "in:" in data:
                #print 'found in: in the incoming message' # #lines=data[data.find("in:")+3:].splitlines()   # vaikesed tahed
                inum=eval(data[data.find("in:")+3:].splitlines()[0].split(',')[0]) # loodaks integerit
                if inum >= 0 and inum<65536:  # valid inum, response to message sent if 1...65535. datagram including "in:0" is a server initiated "fast communication" message
                    #print "found valid inum",inum,"in the incoming message " # temporary
                    print "got ack",inum,
                    
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
                        sys.stdout.flush()
                        #time.sleep(1)
                        #traceback.print_exc() 
                        
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
                                print " ERROR: there are still",row[0],"rows in buff2server with inum",inum
                            else:
                                print ', rows with inum',inum,'deleted from buff2server'
                    
                    except:
                        print 'trouble with',Cmd1
                        sys.stdout.flush()
                        #time.sleep(1)
                        #traceback.print_exc()
                            
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
                                print "  got setup/cmd data reg val", sregister, svalue # need to reply in order to avoid retransmits of the command(s)
                                sendstring=sendstring+sregister+":"+svalue+"\n"  # add to the answer
                                
                                if sregister<>'cmd': # can be variables to be saved into asetup table. does not accept anything that are not in there already!
                                    print 'need for setup change detected due to received',sregister,svalue,', setup_change so far',setup_change
                                    if setup_change == 0: # first setup variable inthe message found (there can be several)
                                        setup_change=1 # flag it
                                        sCmd="BEGIN IMMEDIATE TRANSACTION" # asetup table. there may be no setup changes, no need for empty transactions
                                        try:
                                            conn4.execute(sCmd) # setup transaction start
                                            print 'transaction for setup change started'
                                        except:
                                            print 'setup change problem'
                                            sys.stdout.flush()
                                            #time.sleep(1)
                                            #traceback.print_exc()
                                        
                                    else: # already started
                                        print 'setup_change continues' # debug

                                    
                                    sCmd="update asetup set value='"+str(svalue)+"', ts='"+str(int(ts))+"' where register='"+sregister+"'" # update only, no insert here!
                                    print sCmd # debug
                                    try: # if not succcessful, then not a valid setup message
                                        conn4.execute(sCmd) # table asetup/asetup
                                        print 'setup change done',sregister,svalue
                                    except:
                                        print 'assumed setup register',sregister,'not found in setup table! value',svalue,'ignored!'
                                        #traceback.print_exc() # temporary debug only

                                else: # must be cmd, not to be saved into asetup table
                                    print 'remote command detected due to received',sregister,svalue
                                    if TODO == '': # no change if not empty
                                        TODO=svalue # command content to be parsed and executed
                                        print 'TODO set to',TODO
                                    else:
                                        print 'could not set TODO to',svalue,', TODO still',TODO
                                        
                            # all members that are not in por id are added to sendstring
                            if sendstring<>'':
                                udpsend(0,int(ts))  # send back the ack for commands. this adds in and id always. no need for server ack, thus 0 instead of inumm
                            
                    if setup_change == 1: #there were some changes done  to asetup
                        conn4.commit() # transaction end for setup change. what if no changes were needed?
                        setup_change=0 #back to normal
                        if TODO == '':
                            TODO='VARLIST' # let's report setup without asking if setup was changed
                        else: # not empty, something still not done?
                            print 'could not set TODO to VARLIST, was not empty:',TODO
                                
                    #####
                    
                else: # invalid inum
                    print "invalid inum",inum,"from server",repr(data)
            
                
                
                 
            else: # in: missing, this is abnormal
                print "no in: found in server response!"
                
            
            
            
            
        else:
            print ts, "illegal message (no id present) from", str(addr)
            print repr(data) # with visible newline chars

    except:  # no new data in 0.1s waiting time
        #print '.',  #currently no udp response data on input, printing dot
    
        #something to do? 
        
        if TODO <> '': # yes, it seems there is something to do
            if TODO == 'VARLIST': # report setup to the server
                report_setup() # report all asetup table content to server
            
            if TODO.split(',')[0] == 'update': # download a file (with name and size given)
                if update(TODO) == 0: # success. filename and size as parameters. SUPPORTHOST is global var.
                    print 'remote command',TODO,'successfully fulfilled'
                else:
                    print 'remote command',TODO,'execution failed!'
                    
                
            if TODO == 'VARLIST' == 'REBOOT': # reboot, just the application or android as well??
                print 'rebooting, but how and what?'
                
            TODO=''
            print 'remote command processing done'
            sys.stdout.flush()
            #time.sleep(1)
            
        # ending processing the things to be done


    
    # ####### now other things like making services messages to send to the monitoring server and launching REGULAR MESSANING ########
    ts=time.mktime(datetime.datetime.now().timetuple()) #time in seconds now
        
    if ts>appdelay+ts_lastappmain:  # time to read analogue registers and counters, not too often
        # this is the appmain part below
        print 'a', #   "appmain start at",ts,">",appdelay+ts_lastappmain,"appdelay",appdelay
        ts_lastappmain=ts # remember the execution time
  
        read_aichannels() # read analogue channels and put data into buff2server table to be sent to the server
        read_counters() # read counters (2 registers usually, 32 bit) and put data into buff2server table to be sent to the server
    
        # ############################################################ temporary check to debug di part here, not as often as normally
        #read_dichannel_bits() # di read as bitmaps from registers. use together with the make_dichannel_svc()!
        #make_dichannel_svc() # di related service messages creation, insert message data into buff2server to be sent to the server
        #write_dochannels() # compare the current and new channels values and use write_register() to control the channels to be changed with 
        # end di part. put into fastest loop for fast reaction!
        # ###########################################################
        
        
        if ts>renotifydelay+ts_lastnotify:  # regular messaging not related to registers but rather to program variables
            #print "renotify application variables dut to ts",ts,">",appdelay+ts_lastappmain,", appdelay",appdelay
            ts_lastnotify=ts # remember timestamp
            
            #testdata() # test services / can be used instead of read_*()
            #unsent()  # unsent by now. chk using renotifydelay to send again or delete of too old. vigane! kustutab ka selle, mis on vaja saata!
            
            if ts>ts_boot + 20: # to avoid double messsaging on startup
                sendstring="UPV:"+str(int(ts-ts_boot))+"\nUPS:" # uptime value in seconds
                if int(ts-ts_boot)>1800: # status during first 30 min of uptime is warning, then ok
                    sendstring=sendstring+"0\n" # ok
                else:
                    sendstring=sendstring+"1\n" # warning
                    
                udpsend(0,int(ts)) # SEND AWAY. no need for server ack so using 0 instead of inumm
    
    # REGULAR MESSAGING RELATED PART END (AI, COUNTERS)   

       
    # ###### NOW THE THINGS TO DO MORE OFTEN, TO BE REPORTED ON CHANGE OR renotifydelay TIMEUT (INDIVIDUAL PER SERVICE!) ##########
    read_dichannel_bits() # di read as bitmaps from registers. use together with the make_dichannel_svc()!
    make_dichannel_svc() # di related service messages creation, insert message data into buff2server to be sent to the server # tmp OFF!
    write_dochannels() # compare the current and new channels values and use write_register() to control the channels to be changed with 
    
    # control logic FOR OUTPUTS goes to a separate script, manipulating dochannels only. ##################    
    
    #check tcp socket health, restart also if tcperr too high (consequetive errors)
    if tcperr>4:
        print 'restarting tcpsocket due to 5 consequetive errors on modbus'
        socket_restart()
        tcperr=0 # restart counter        
        sys.stdout.flush()
        time.sleep(0.5) # soocket restart
        
    udpmessage() # chk buff2server for messages to send or resend. perhaps not on the fastest possible rate? 
    #but immediately if there as a change in dichannels data. no problems executong every time if select chg is fast enough...
    
    print '.', # dots are signalling the fastest loop executions here
    
    sys.stdout.flush() # to update the log for every dot
    

    
#main end. main frequency is defined by udp socket timeout!
######## END  ######################
