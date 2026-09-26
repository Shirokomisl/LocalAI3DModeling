$p='C:\AI\local-3d-agent\scripts\generate.py'
$s=[IO.File]::ReadAllText($p)
$old=@'
    candidate=(dist<30).astype(np.uint8)
    nbg,lab,stats,_=cv2.connectedComponentsWithStats(candidate,8)
    for i in range(1,nbg):
        x,y,ww,hh,area=stats[i]
        touches=(x==0 or y==0 or x+ww>=w or y+hh>=h)
        if touches or area > 0.003*h*w:
            alpha[lab==i]=0
'@
$new=@'
    candidate=(dist<15).astype(np.uint8)
    nbg,lab,stats,_=cv2.connectedComponentsWithStats(candidate,8)
    for i in range(1,nbg):
        area=int(stats[i,cv2.CC_STAT_AREA])
        if area>10000:
            alpha[lab==i]=0
'@
if(!$s.Contains($old)){throw 'target not found'}
[IO.File]::WriteAllText($p,$s.Replace($old,$new),[Text.Encoding]::UTF8)
