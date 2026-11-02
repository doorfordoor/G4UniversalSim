# Linux 原生显示依赖边界

Ubuntu实际系统安装 x11-xkb-utils 7.7+8build2，dpkg退出0，原因是Xvnc内置/usr/bin/xkbcomp路径；原二进制SHA与已核官方包匹配。libxcb-cursor0及TigerVNC/twm等其它本次依赖保持OUT隔离，未作为系统安装。historical-isolated-display-preparation.json中的system_installs=0仅记录准备时点，不覆盖后续真实安装。此处只公开三个原JSON收据、字节清单与边界，不含.deb、EXE或安装树。
