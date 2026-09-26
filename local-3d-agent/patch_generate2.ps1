$p='C:\AI\local-3d-agent\scripts\generate.py'
$s=[IO.File]::ReadAllText($p)
$old=@'
        if touches:
            alpha[lab==i]=0
'@
$new=@'
        if touches or area > 0.003*h*w:
            alpha[lab==i]=0
'@
if(!$s.Contains($old)){throw 'target not found'}
[IO.File]::WriteAllText($p,$s.Replace($old,$new),[Text.Encoding]::UTF8)
