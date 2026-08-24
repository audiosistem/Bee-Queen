# -*- coding: utf-8 -*-
# RomyLive protected runtime loader
import base64 as _b, zlib as _z
_p = (
    'c-nneOK;;g5WeeI5ZQyR!d8>*9@+qV2x4zwG%q+wfp!x(6h&E#DN-OQ$4<Ndy~BrONonefNseYX^Uaf=(DbJ%A~IuQeTr(6Pk*&1(b3USw3Oxkl5HuPqTlKM'
    'RjLf7SknxV0t-PoA{=YYaz+)(r9#WuUBd16ni9jLNTO(2bE*+m6yd7k40xG9+9*a00(rnV&Y98%mDrF1y)vQW1l<=*BSp33TgzRhY+W<MsE#<>P;@k7YliMB'
    'smu`?yZ;z%bvXb0#U2`_SPTlBV?)<c0q<#q;5S8QS<MX#8^;{h=dxn$x#bV*nIv^dg#jzV$yNQv2o9TXjF%1Jf(oiIXWCHoGnxSw$}nx28(H>9Q?MFyo?^0z'
    'qv!$l&jHH)Sm2Vz&&Wu$rUsdUBH~ThJB)D)zWp%q%;#tK^NXA1pR1eYY`%2N%zz@MWd{2#@)^?=$9oTb;+!0@(qaH`16Ylmv)RMt{Q`YOBahbTK)SoVS>9WU'
    'gRVn3zqwsF7KdY(<9@Mp1P5w|FuOT_xSC(zpDpK>+`+l?(bdCWi}N!}_o#PB-xilwj?=lIL%5h<&zEPHi@SSA{@5#BWfp(Tmv>$f@1#)_eL^=bNCCRnf<b_G'
    ';CyAAqm(w7`p~xidRQb;-y<OOy9<E6>XZJNLw0y(u^XH@pa*9jrNLnb-vOlq(17ASKNRG#nM6+(l91COpN*`hMov>{j4Tt#hJH3Dz%a+K0kqZr6pfo`UfKAa'
    'AnTQt%vT#<VDt*>m0hf)T2+ODauY|Z<-_Itt_5*CR5qO3pBn9UyU_&xu?<|eDr#*wRc>7=wgm;;I#u}X4IJ$W;KEeyN0W}I$Fz{<F?DpRq?cQPA%(29m$7AA'
    'miZMGwHK91MJVq{B3NX5M^qF7(d^L%>aG7g<uyfJ9W~t<MIoTQgr|5iFxv-8&uZ<G(J5LhdDvx=6R5}S{xRiJZh}n!Mu{6@M_6XdXh#NY4?D-y6)18Z<iR?{'
    'cHP5pEqNY3FjNTUt<KrH@Dl2rcpT&oFmcOL8mW3>6ebN3s$f}jj84Lx`AK`_d#HS_^q|_X%&S1KGE$00bw(Oo?2>Ys(LjU@7qlN5sgxzulty1B02Ch|FSTIO'
    'J2J(ocY21=mI=aoB3@XDUU2C@sL2MItrteu*a`c{`>rJPOcM0fo1|TZbq3YPpHF^kx7LTBzqCta*Bt>^fNL=Nr4yo%B{)Enp0o~5Ps}!Klq|7e*s0xfI1!>r'
    '8i>VKw=^XPGMi`Zt|ehkt70HUU|lzXB~wim<gHYlxNW)3))weo_G6gVMiZ#UuaxtTQ>j}bdys<9iG()b9VoDYb}XAU%r=<YgSEmH^aWpLppr?oAK(g_as<Ui'
    'P!kFU*0@QX3_6}SLE)_}8UFOYqD2!%1@T3Pfc<{O1Pn-qt({7Non-+vS6G^>Kd?Xajh^Xct%FIAY1z7a!?bP=@tTpw#YT8opl#!P;KLfV>?i0Twt~dl2h2?8'
    '{H=Z;Oc@5N+wjXJ-?SSDKgt`LVy2WIn(5nZ&q}B#w8Wv@Y#D8CfKehWi&VCE;hi|FOY*MB(W*tHkeov=lUWGPljGy#Q1W=0hA!f7-wln0=F~W^C&iN9SRfH7'
    'J=q=++fgw;)C_Bd{t$w0%kKg4m{zJW)Yk#;Z!B;VkuKpH^PutXdx<bG0@AUkXybBFuok9u<Su;lij|=KVqa3DWF@&*1QW;@-zh?cq&4&ahC8OZx#U(+xUpiK'
    '!Z5q0J5<5s)(+2O4GjcHn8Rf3RquSJV5V{NwXP`5;NbwB<LY*CIiK0F!wxNQF-?N}@#vpX@*<fSSJ>#-kro%%H_Q3?+1)&jog~L&>2@ykBMhh+Wi&_aupef5'
    'Hw(r7fdVu6lA2nHgX$coFz>&g{!wjhLhb=I^&^)X>|rXi_UOdU_f{s$k&p&;Z#zBU?Qa_ndyejI`PySl?CY%>$By2$)57XZZIC-$0r!Uw5>2rp#kgbeKo1ZX'
    '{hwNW1Xu8kYEabg5X|f|^X~@7Q}jK2IYCL1JpDiwyfLA%SP=UIJ3Jh%q~}KRGlB;x7XDS0La4~x3Ae8RQy}OLoMM=JF&bIRMhM2)q*2EGr_kXkeE${n0Y#oX'
    'bQZ7v%|8yf7M9v*aKH-8u`W4;Py!FdvA=hMMx!`xKMj`x=mtQ;FcAAl{{9pvkj7MGz#ezu4jj?HZ1v9='

)
exec(compile(_z.decompress(_b.b85decode(_p.encode('ascii'))), __file__, 'exec', optimize=2), globals(), globals())
