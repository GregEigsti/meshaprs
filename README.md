# meshaprs

Meshtastic Python API required!
See: https://meshtastic.org/docs/software/python/cli/installation/

To start the iGate
python3 igate.py

keyboard commands:
a => show APRS participants sent to the APRS-IS
c => show available commands
e => show nodes using encryption
i => broadcast ident
m => show received messages
n => show nodes table
q => quit
sb <ch-index> <message> => send broadcast message
sd <to> <message> => send direct message

Message send examples (keyboard commands)
sb 0 this is a test broadcast message to channel 0
sd !10a37e85 this is a direct message to !10a37e85

Over the air RF commands (received on Meshtastic RF network)
"about" this iGate.
"commands" to list possible commands.
"git" link to this server's python source code.
"ping" to receive pong