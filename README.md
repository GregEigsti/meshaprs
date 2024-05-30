# meshaprs

[Meshtastic Python API](https://meshtastic.org/docs/software/python/cli/installation/) required!

To start the iGate: **python3 igate.py**

**keyboard commands**\
keyboard commands:\
a  => show APRS participants sent to the APRS-IS\
b  => show bogotrons\
c  => show available commands\
e  => show nodes using encryption\
i  => broadcast ident\
m  => show received messages\
n  => show neighbors\
nt => show nodes table\
q  => quit\
r  => heard since starting\
sb \<ch-index\> \<message\> => send broadcast message\
sd \<to> \<message\> => send direct message

**Message send examples (keyboard commands)**\
sb 0 this is a test broadcast message to channel 0\
sd !10a37e85 this is a direct message to !10a37e85

**Over the air RF commands (received on Meshtastic RF network)**\
"?about" this iGate.\
"?commands" to list possible commands.\
"?git" link to this server's python source code.\
"ping" to receive pong.\
"?wx-current" to receive current local weather.\
"?wx-forecast" to receive forecasted local weather.
