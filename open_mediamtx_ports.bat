@echo off
echo Opening firewall ports for PineVision MediaMTX...
netsh advfirewall firewall add rule name="PineVision MediaMTX RTMP"  dir=in action=allow protocol=TCP localport=1935
netsh advfirewall firewall add rule name="PineVision MediaMTX HLS"   dir=in action=allow protocol=TCP localport=8888
netsh advfirewall firewall add rule name="PineVision MediaMTX RTSP"  dir=in action=allow protocol=TCP localport=8554
echo Done. DJI Fly can now reach the RTMP server on port 1935.
pause
