#!/usr/bin/env python
import usb
import sys
import struct
import pprint
import argparse
import StringIO

pp = pprint.PrettyPrinter()

class ConsoleUI:
  def opStart(self, name):
    sys.stdout.write(name.ljust(40))
    
  def opProgress(self,progress, total=-1):
    if (total >= 0): 
      prstr = "0x%04x / 0x%04x" % (progress, total)
    else:
      prstr = "0x%04x" % (progress)
      
    sys.stdout.write(prstr.ljust(20))
    sys.stdout.write('\x08' * 20)
    sys.stdout.flush()
    
  def opEnd(self, result):
    sys.stdout.write(result.ljust(20))
    sys.stdout.write("\n")

class DeviceNotFoundError(Exception):
    pass

CMD_DATA_READ   = 0x01
CMD_DATA_WRITE  = 0x02
CMD_DATA_INIT   = 0x03
CMD_DATA_DEINIT = 0x04
CMD_DATA_STATUS = 0x05
CMD_DATA_ERASE  = 0x06
CMD_DEV_VERSION = 0x08
CMD_XSVF_EXEC   = 0x09
CMD_XBOX_PWRON  = 0x10
CMD_XBOX_PWROFF = 0x11
CMD_DEV_UPDATE  = 0xF0

class XFlash2(object):
    def __init__(self, idVendor=0xffff, idProduct=0x4):
        self.idVendor = idVendor
        self.idProduct = idProduct
        self.dev = None
    
    def deviceFind(self):
        self.dev = usb.core.find(idVendor=self.idVendor,
                                 idProduct=self.idProduct)
        
        if self.dev is None:
            raise DeviceNotFoundError(self.idVendor, self.idProduct)
        
        self.dev.set_configuration()
        
        self.ep_out = 0x05
        self.ep_in  = 0x82
    
    def deviceReset(self):
        if self.dev is None:
            return
        
        self.dev.reset()
        self.dev.set_configuration()
    
    def deviceCmd(self, cmd, argA=0, argB=0, timeout=None):
        buffer = struct.pack('<LL', argA, argB)
        self.dev.ctrl_transfer(bmRequestType    = usb.TYPE_VENDOR,
                               bRequest         = cmd,
                               wValue           = 0,
                               wIndex           = 0,
                               data_or_wLength  = buffer,
                               timeout          = timeout)
    
    def deviceUpdate(self):
        try:
            self.deviceCmd(CMD_DEV_UPDATE)
        except: pass
    def deviceVersion(self):
        self.deviceCmd(CMD_DEV_VERSION, 0 , 4)
        buffer = self.dev.read(self.ep_in, 4) # read 4 bytes
        buffer = ''.join([chr(x) for x in buffer])
        return struct.unpack('<L', buffer)[0]
        
    def xsvfInit(self):
        self.deviceReset()
        self.deviceVersion()
        self.deviceVersion()
        return self.deviceVersion()
    
    def xsvfWrite(self, buffer):
        self.deviceCmd(CMD_DATA_WRITE, 0, len(buffer))
        self.dev.write(self.ep_out, buffer, timeout=1000)
    
    def xsvfExecute(self):
        self.deviceCmd(CMD_XSVF_EXEC, timeout=10000)
        return self.flashStatus()
    
    def __flash_status(self, cmd=None):
        if not cmd is None:
            self.deviceCmd(cmd)
        
        buffer = self.dev.read(self.ep_in, 4) # read 4 bytes
        buffer = ''.join([chr(x) for x in buffer])
        return struct.unpack('<L', buffer)[0]
    
    def flashInit(self):
        return self.__flash_status(CMD_DATA_INIT)
    
    def flashDeInit(self):
        self.deviceCmd(CMD_DATA_DEINIT)
    
    def flashStatus(self):
        return self.__flash_status(CMD_DATA_STATUS)
    
    def flashErase(self, block):
        self.deviceCmd(CMD_DATA_ERASE, block)
        return self.flashStatus()
    
    def flashRead(self, block):
        self.deviceCmd(CMD_DATA_READ, block, 0x4200)
        buffer = self.dev.read(self.ep_in, 0x4200)
        buffer = ''.join([chr(x) for x in buffer])
        status = self.flashStatus()
        return (status, buffer)
    
    def flashWrite(self, block, buffer):
        self.deviceCmd(CMD_DATA_WRITE, block, len(buffer))
        self.dev.write(self.ep_out, buffer)
        return self.flashStatus()
    
    def consolePowerOn(self):
        self.deviceCmd(CMD_XBOX_PWRON)
    
    def consolePowerOff(self):
        self.deviceCmd(CMD_XBOX_PWROFF)

# def calcecc(data):
#   assert len(data) == 0x210
#   val = 0
#   for i in range(0x1066):
#     if not i & 31:
#       v = ~struct.unpack("<L", data[i/8:i/8+4])[0]
#     val ^= v & 1
#     v >>= 1
#     if val & 1:
#       val ^= 0x6954559
#     val >>= 1
# 
#   val = ~val
#   return data[:-4] + struct.pack("<L", (val << 6) & 0xFFFFFFFF)
# 
# def addecc(data, block = 0, off_8 = "\x00" * 4):
#   res = ""
#   while len(data):
#     d = (data[:0x200] + "\x00" * 0x200)[:0x200]
#     data = data[0x200:]
# 
#     d += struct.pack("<L4B4s4s", block / 32, 0, 0xFF, 0, 0, off_8, "\0\0\0\0")
#     d = calcecc(d)
#     block += 1
#     res += d
#   return res

def compress(ib):
    ob = StringIO.StringIO()
    
    rs = re = rl = 0
    lb = 0
    while rs < len(ib):
        # check for repeat
        if ib[rs] == ib[rs + 1]:
            re = rs
            while re < len(ib) and ib[rs] == ib[re]:
                re += 1
            rl = re - rs
            ob.write(ib[rs:rs+2])
            ob.write(chr(rl - 2))
            rs += rl
        else:
            ob.write(ib[rs])
            rs += 1
    return ob.getvalue()

def main(argv=sys.argv):
    parser = argparse.ArgumentParser(description='XBox 360 NAND Flasher')
    subparsers = parser.add_subparsers(title='Operations', dest='action')
    
    parser_read = subparsers.add_parser('read', help='Dumps an image from the NAND')
    parser_read.add_argument('file', nargs=1, type=argparse.FileType('w'), help='The file to dump the NAND to')
    parser_read.add_argument('start', nargs='?', metavar='start', action='store', type=int, default=0, help='The block to start the action from')
    parser_read.add_argument('end', nargs='?', metavar='end', action='store', type=int, default=0x400, help='The count of blocks to perform the action to')
    
    parser_write = subparsers.add_parser('write', help='Writes an image into the NAND')
    parser_write.add_argument('file', nargs=1, type=argparse.FileType('r'), help='The image file to write to the NAND')
    parser_write.add_argument('start', nargs='?', metavar='start', action='store', type=int, default=0, help='The block to start the action from')
    parser_write.add_argument('end', nargs='?', metavar='end', action='store', type=int, default=0x400, help='The count of blocks to perform the action to')
    
    parser_erase = subparsers.add_parser('erase', help='Erases blocks in the NAND')
    parser_erase.add_argument('start', nargs='?', metavar='start', action='store', type=int, default=0, help='The block to start the action from')
    parser_erase.add_argument('end', nargs='?', metavar='end', action='store', type=int, default=0x400, help='The count of blocks to perform the action to')
    
    parser_xsvf = subparsers.add_parser('xsvf', help='Flash a CPLD with an xsvf file')
    parser_xsvf.add_argument('file', nargs=1, type=argparse.FileType('r'), help='The xsvf file to read from')
    
    parser_update = subparsers.add_parser('update', help='Jumps into the bootloader of the NAND Flashing device for updating the firmware')
    parser_shutdown = subparsers.add_parser('poweroff', help='Shuts down the attached XBox 360')
    parser_poweron = subparsers.add_parser('poweron', help='Powers up the attached XBox 360')
    
    arguments = parser.parse_args(argv[1:])
    
    ui = ConsoleUI()
    xf = XFlash2()
    
    try:
        xf.deviceFind()
    except DeviceNotFoundError:
        print 'XFlash USB device not found'
        sys.exit(1)
    
    xf.deviceReset()
    
    print "Using XFlash @ [%s:%s]" % (xf.dev.bus, xf.dev.address)
    if arguments.action in ('erase', 'write', 'read'):
        try:
            print "FlashConfig: 0x%08x" % (xf.flashInit())
        except:
            xf.flashDeInit()
    
    if arguments.action == 'erase':
        start = arguments.start
        end = arguments.end
        
        ui.opStart('Erase')
        
        for b in range(start, end):
            ui.opProgress(b, end-1)
            status = xf.flashErase(b)
        
        ui.opEnd('0x%04x blocks OK' % (end))
    
    if arguments.action == 'read':
        start = arguments.start
        end = arguments.end
        
        ui.opStart('Read')
        
        for b in range(start, end):
            ui.opProgress(b, end-1)
            (status, buffer) = xf.flashRead(b)
            arguments.file[0].write(buffer)
    
    if arguments.action == 'write':
        start = arguments.start
        end = arguments.end
        blocksize = 528 * 32
        
        ui.opStart('Write')
        
        for b in range(start, end):
            ui.opProgress(b, end-1)  
            buffer = arguments.file[0].read(blocksize)
            if len(buffer) < blocksize:
                buffer += ('\xFF' * (blocksize-len(buffer)))
            status = xf.flashWrite(b, buffer)
    
    if arguments.action == 'xsvf':
        vers = xf.xsvfInit()
        print 'ARM Version %s' % (vers)
        fbuffer = arguments.file[0].read()
        print 'Read 0x%x bytes OK' % (len(fbuffer))
        buffer = compress(fbuffer)
        print 'Compressed to 0x%x bytes OK' % (len(buffer))
        xf.xsvfWrite(buffer)
        print '0x%x bytes sent OK' % (len(buffer))
        print 'Executing File...',
        sys.stdout.flush()
        status = xf.xsvfExecute()
        print 'OK!' if status == 0 else 'FAIL!'
        xf.deviceReset()
    
    if arguments.action == 'update':
        xf.deviceUpdate()
    
    if arguments.action == 'poweron':
        xf.flashPowerOn()
    
    if arguments.action == 'poweroff':
        xf.flashPowerOff()


if __name__ == '__main__':
    main(sys.argv)
    print