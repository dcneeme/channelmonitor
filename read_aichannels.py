def read_aichannels(): # analogue inputs via modbusTCP, to be executed regularly (about 1..3 s interval). do not send here.
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
        cursor3.execute(Cmd3)
        
        for row in cursor3: # services
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
            cursor3a.execute(Cmd3) # another cursor to read the same table

            for srow in cursor3a: # service members
                #print repr(srow) # debug
                mba=-1 # 
                regadd=-1
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
                ovalue=0 # previous (possibly averaged) value
                ots=0 # eelmine ts value ja status ja raw oma
                avg=0 # keskmistamistegur, mojub alates 2
                desc=''
                comment=''
                # 0       1     2     3     4   5  6  7  8  9    10     11  12    13  14   15     16  17    18
                #mba,regadd,val_reg,member,cfg,x1,x2,y1,y2,outlo,outhi,avg,block,raw,value,status,ts,desc,comment  # aichannels
                if srow[0]<>'':
                    mba=int(srow[0]) # must be int! will be -1 if empty (setpoints)
                if srow[1]<>'':
                    regadd=int(srow[1]) # must be int! will be -1 if empty
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
                    avg=int(srow[11])  #  averaging strength, values 0 and 1 do not average!
                if srow[12]<>'': # block - loendame siin vigu, kui kasvab yle 3? siis enam ei saada
                    block=int(srow[12])  #  
                if srow[13]<>'': # 
                    oraw=int(srow[13])
                if srow[14]<>'': 
                    ovalue=int(srow[14])
                if srow[15]<>'':
                    ostatus=int(srow[15])
                if srow[16]<>'':
                    ots=int(srow[16])
                desc=srow[17]
                comment=srow[18]

            
                if mba>=0 and mba<256 and regadd>=0 and regadd<65536:  # valid mba and regaddr, let's read to update value in aichannels table
                    print 'reading ai',mba,regadd,'for',val_reg,'m',member,  # ajutine
                    
                    respcode=read_register(mba,regadd,1)  #  READING THE AI REGISTER
                    if respcode == 0: # got  tcpdata as register content. convert to scale.
                        #print 'value',tcpdata
                        tcperr=0
                            
                        if x1<>x2 and y1<>y2: # sisendandmed usutavad
                            value=(tcpdata-x1)*(y2-y1)/(x2-x1)
                            value=y1+value 
                            
                            #print 'raw',tcpdata,', ovalue',ovalue, # debug
                            if avg>1 and abs(value-ovalue)<value/2: # keskmistame, hype ei ole suur
                            #if avg>1:  # lugemite keskmistamine vajalik, kusjures vaartuse voib ju ka komaga sailitada!
                                value=((avg-1)*ovalue+value)/avg # averaging
                                print ', averaged',value
                            else: # no averaging for big jumps
                                if tcpdata == 4096: # this is error result from 12 bit 1wire temperature sensor
                                    value=ovalue # repeat the previous value. should count the errors to raise alarm in the end! counted error result is block, value 3 stps sending. 
                                else: # acceptable non-averaged value
                                    print ', no averaging, value',value
                                
                        else:
                            print "val_reg",val_reg,"member",member,"ai2scale PARAMETERS INVALID:",x1,x2,'->',y1,y2,'value not used!'
                            value=0 
                            status=3 # not to be sent status=3! or send member as NaN? 
                    
                    else: # failed reading register, respcode>0
                        tcperr=tcperr+1 # increase error counter
                        print 'failed to read ai register', mba,regadd,'respcode',respcode
                        if respcode >0:
                            return 1
                
                else:
                    value=ovalue # possible setpoint, ovalue from aichannels table, no modbus reading for this
                    status=0
                    #print 'setpoint value',value
            
                
                # check the value limits and set the status, acoording to configuration byte cfg bits values
                # use hysteresis to return from non-zero status values
                status=0 # initially for each member
                if value>outhi: # above hi limit
                    if (cfg&4) and status == 0: # warning 
                        status=1
                    if (cfg&8) and status<2: # critical 
                        status=2
                    if (cfg&12): #  not to be sent
                        status=3
                        block=block+1 # error count incr
                else: # return with hysteresis 5%
                    if value>outlo and value<outhi-0.05*(outhi-outlo): # value must not be below lo limit in order for status to become normal
                        status=0 # back to normal
                        block=0 # reset error counter
                
                if value<outlo: # below lo limit
                    if (cfg&1) and status == 0: # warning
                        status=1
                    if (cfg&2) and status<2: # critical
                        status=2
                    if (cfg&3): # not to be sent, unknown
                        status=3
                        block=block+1 # error count incr
                else: # back with hysteresis 5%
                    if value<outhi and value>outlo+0.05*(outhi-outlo):
                        status=0 # back to normal
                        block=0
                        
                #print 'status for AI val_reg, member',val_reg,member,status,'due to cfg',cfg,'and value',value,'while limits are',outlo,outhi # debug
                #aichannels update with new value and sdatus
                Cmd3="UPDATE aichannels set status='"+str(status)+"', value='"+str(value)+"', ts='"+str(int(ts))+"' where val_reg='"+val_reg+"' and member='"+str(member)+"'" # meelde
                #print Cmd3 
                conn3.execute(Cmd3) # kirjutamine
            
        conn3.commit() # aichannels transaction end
        
    except:
        msg='PROBLEM with aichannels reading or processing at'+str(int(ts))
        print(msg)
        log2file(msg)
        traceback.print_exc()
        sys.stdout.flush()
        time.sleep(0.5)
        
    #read_aichannels end