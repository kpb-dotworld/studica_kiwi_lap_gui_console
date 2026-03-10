charansc@charansc-Zenbook:~/Documents/Nationals/studica_gui/control_station$  ps aux | grep kiwi_dashboard | grep -v grep
charansc    7377  0.8  0.4 1164664 67220 pts/1   Tl   10:09   0:02 python3 kiwi_dashboard.py
charansc    7838  0.7  0.4 942160 65088 pts/1    Tl   10:10   0:02 python3 kiwi_dashboard.py
charansc@charansc-Zenbook:~/Documents/Nationals/studica_gui/control_station$  curl -s http://localhost:8080/ | head -20
^C
charansc@charansc-Zenbook:~/Documents/Nationals/studica_gui/control_station$  pkill -9 -f "kiwi_dashboard" || true; sleep 2
charansc@charansc-Zenbook:~/Documents/Nationals/studica_gui/control_station$  python3 kiwi_dashboard.py > /tmp/server.log 2>&1 &
[1] 13471
charansc@charansc-Zenbook:~/Documents/Nationals/studica_gui/control_station$  sleep 3 && curl -s http://localhost:8080/ | head -5
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
charansc@charansc-Zenbook:~/Documents/Nationals/studica_gui/control_station$ 
