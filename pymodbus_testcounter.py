#!/usr/bin/python
# yritan aru saada kuidas pymodbus abil mitut registrit jarjest lugeda

import time
import sys
from pymodbus.client.sync import ModbusTcpClient

#############################################################################
ip=sys.argv[1].split(':')[0] # '10.0.0.13' #'10.0.0.105' # '176.124.247.38'
port=sys.argv[1].split(':')[1] # '502' # '10502' # miks string?
print 'ip',ip,'port',port

pic=[1]        # PIC address(es) [1, ... ]
io12=[]        # IO12 addresses [1, 2, 3, ... ]

#############################################################################

# http://code.activestate.com/recipes/142812-hex-dumper/
FILTER=''.join([(len(repr(chr(x)))==3) and chr(x) or '.' for x in range(256)])
def dump(src, length=8, N=0):
    result=''
    while src:
        s,src = src[:length],src[length:]
        hexa = ' '.join(["%02X"%ord(x) for x in s])
        s = s.translate(FILTER)
        result += "%5d (%04X)  %-*s   %s\n" % (N, N, length*3, hexa, s)
        N+=(length/2)
    return result

def showreg(client, unit, reg, l, dlen=16):
    s = 'unit='
    s += str(unit)
    s += ' | reg='
    s += str(reg)
    s += ':'
    s += str(l)
    s += '\n'
    x = ''
    try:
        result = client.read_holding_registers(address=reg, count=l, unit=unit)
        for i in result.registers:
            x += format("%04x" % i)
        if dlen > (l * 2):
            dlen = (l * 2)
        s += dump(x.decode('hex'), length=dlen, N=reg)
    except:
        s += ' ****** ERROR ******\n'
    print s

def show_modpusbprxy(client):
        showreg(client, 255, 0, 30)
        showreg(client, 255, 100, 30)
        showreg(client, 255, 101, 30)
        showreg(client, 255, 200, 1)
        showreg(client, 255, 300, 8)
        showreg(client, 255, 301, 30)
        showreg(client, 255, 302, 30)
        showreg(client, 255, 303, 30)
        showreg(client, 255, 304, 1)
        showreg(client, 255, 305, 1)
        showreg(client, 255, 310, 3)
        showreg(client, 255, 313, 2)

def show_io12(client):
    for addr in io12:
        showreg(client, addr, 0, 2)
        showreg(client, addr, 256, 16)
        showreg(client, addr, 274, 1)
        showreg(client, addr, 275, 1)

def show_pic(client):
    for addr in pic:
        showreg(client, addr, 0, 1)
        showreg(client, addr, 1, 1)
        showreg(client, addr, 2, 8, 2)
        showreg(client, addr, 10, 1)
        showreg(client, addr, 11, 10, 10) # wiegand
        #showreg(client, addr, 255, 1)
        showreg(client, addr, 258, 2)
        showreg(client, addr, 271, 9, 2) # config registers
        showreg(client, addr, 400, 16, 4)  # counters, 4 bytes
        showreg(client, addr, 600, 9, 2)  # temp ds18b20 data
        showreg(client, addr, 650, 4 * 9, 8)   # ds18b20 id
        showreg(client, addr, 700, 9, 2)  # ds2348 data
        showreg(client, addr, 750, 4 * 9, 8) # 2348 id

        
def show_bn(client):
    showreg(client, 0, 0, 1) #  relee 1
    showreg(client, 0, 1, 1) #  relee 2
    showreg(client, 0, 400, 1) # loendi
    showreg(client, 0, 401, 1)
    showreg(client, 0, 412, 2) # loendi  2 sona jarjest
    showreg(client, 0, 412, 4, 4) # loendi 16 registrit jarjest 4 baidised loendid
        
def reset_pic_counters(client):
    for addr in pic:
        for reg in range(400, 414, 2):
            try:
                client.write_registers(address=reg, values=[reg*100, (reg+1)*100], unit=addr)  # max value 65k
                print 'write ok to',addr,reg,reg*100,(reg+1)*100
            except:
                print 'failed write to',addr,reg,reg*100,(reg+1)*100

client = ModbusTcpClient(host=ip, port=port);

reset_pic_counters(client)
#show_pic(client)
show_bn(client)
#show_modpusbprxy(client)
#show_io12(client)

client.close()
