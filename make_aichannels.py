    

def make_aichannels_svc(): # send the ai service messages to the monitoring server
    locstring="" # local
    global inumm,ts,ts_inumm,mac,tcpdata, tcperr, udpport
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
        conn1.execute(Cmd3) # buff2server
        
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
            #mba,regadd,val_reg,member,cfg,x1,x2,y1,y2,outlo,outhi,avg,block,raw,value,status,ts,desc,comment  # aichannels
            Cmd3="select * from aichannels where val_reg='"+val_reg+"'" # loeme yhe teenuse kogu info uuesti
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
                    print 'reporting ai mba',mba,'.',regadd,'for ',val_reg,'m',member  # ajutine
                else:
                    value=ovalue # possible setpoint, ovalue from aichannels table, no modbus reading for this
                    status=0
                    #print 'setpoint value',value
            
                
                if ostatus>status:
                    status=ostatus
                if status>3:
                    msg='make_aichannels_svs() invalid status '+str(status)
                    print(msg)
                    log2file(msg)
                    
                if lisa<>'': # not the first member
                    lisa=lisa+' ' # separator between member values
                lisa=lisa+str(ovalue) # adding member values into one string
            
            # put together final service to buff2server
            Cmd1="INSERT into buff2server values('"+mac+"','"+host+"','"+str(udpport)+"','"+svc_name+"','"+sta_reg+"','"+str(status)+"','"+val_reg+"','"+str(lisa)+"','"+str(int(ts_created))+"','','')" 
            #print "ai Cmd1=",Cmd1 # debug
            conn1.execute(Cmd1) # write aichannels data into buff2server
 
            
        conn1.commit() # buff2server transaction end
        conn3.commit() # aichannels transaction end
        
    except:
        msg='PROBLEM with aichannels reporting'
        print(msg)
        log2file(msg)
        traceback.print_exc()
        sys.stdout.flush()
        time.sleep(0.5)