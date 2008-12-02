# Makefile.local should define MKHOWTO to point to the Python
# distribution's Doc/tools/mkhowto, e.g.
# MKHOWTO = ${HOME}/cvs/python/dist/src/Doc/tools/mkhowto
include Makefile.local

html=eurasiaguide

html : ${html}
all  : ${html}

%: %.tex
	-rm -fr $@
	${MKHOWTO} $<
	./mkcjk.py $@

clean:
	rm -fr ${html}
	rm -f *.log *.aux *.ind *.idx *.l2h *.toc *.syn *.dvi
