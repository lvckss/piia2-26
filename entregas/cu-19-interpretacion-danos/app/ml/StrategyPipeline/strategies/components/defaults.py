# valores por defecto de threshold compartidos por las tres strategies del
# pipeline (baseline, sahi, geometric ensemble) y por ml/api/core/settings.py.
#
# antes de este modulo cada strategy tenia su propio default hardcodeado
# (baseline=0.3, sahi=0.8, geom_ensemble=0.3, settings.py=0.6), asi que "no
# pasar score_threshold" daba un resultado distinto segun la strategy usada.
#
# si una strategy concreta necesita de verdad un valor distinto (por ejemplo
# geom_ensemble suele calibrarse mas bajo porque filtra por consenso despues),
# ese valor debe pasarse explicitamente en la construccion, nunca quedar como
# default silencioso de la clase.
DEFAULT_SCORE_THRESHOLD: float = 0.6
DEFAULT_MASK_THRESHOLD: float = 0.5
