LATEX=pdflatex
TEXFILES=$(wildcard *.tex)
PDFFILES=$(TEXFILES:.tex=.pdf)

all: $(PDFFILES)

%.pdf: %.tex
	$(LATEX) $<
	$(LATEX) $<  # Run twice for references

clean:
	rm -f *.aux *.log *.out *.pdf *.tex
