"""Capability catalog for the adaptive ISLAM laboratory system.

Only laboratories marked implemented may execute. Planned entries are descriptive
roadmap metadata and can never be dynamically imported or executed by the agent.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Laboratory:
    lab_id: str
    domain: str
    title_ar: str
    status: str
    capabilities: tuple
    limitations: tuple


_LABS = (
    Laboratory(
        "dc_resistive_network", "electronics", "مختبر دوائر DC المقاومة",
        "implemented",
        ("ideal_resistors", "ideal_dc_voltage_sources", "modified_nodal_analysis", "kcl_check"),
        ("لا يحاكي L/C أو AC أو النبضات أو الحرارة أو الضوضاء أو PCB أو تفاوت المكونات",),
    ),
    Laboratory(
        "software_quality", "software", "مختبر البرمجيات والاختبارات",
        "implemented",
        ("allowlisted_unit_tests", "bounded_file_inspection", "build_result_review"),
        ("لا يشغل أوامر shell حرة أو شيفرات غير مصرح بها",),
    ),
    Laboratory("series_rlc", "electronics", "مختبر RLC أحادي الحلقة AC وعابر", "implemented",
               ("series_rlc_ac_phasor", "series_rlc_transient_rk4", "resonance", "phase", "energy_trace"),
               ("نموذج مثالي أحادي الحلقة؛ ليس SPICE عاماً ولا يحاكي أشباه الموصلات أو الطفيليات",)),
    Laboratory("linear_ac_network", "electronics", "مختبر شبكات AC متعددة العقد MNA", "implemented",
               ("multi_node_ac", "resistors", "capacitors", "inductors", "ideal_voltage_sources", "kcl_check"),
               ("نموذج خطي مثالي؛ لا يشمل العناصر غير الخطية أو الطفيليات أو التوافقيات",)),
    Laboratory("transient_circuits", "electronics", "مختبر الدوائر العابرة وRLC", "planned",
               ("capacitors", "inductors", "transient_response", "switching"), ("غير منفذ بعد",)),
    Laboratory("analog_digital_electronics", "electronics", "مختبر الإلكترونيات التناظرية والرقمية", "planned",
               ("op_amp_models", "logic", "adc_dac", "noise", "tolerance"), ("غير منفذ بعد",)),
    Laboratory("embedded_systems", "embedded", "مختبر الأنظمة المضمنة والمتحكمات", "planned",
               ("timers", "interrupts", "peripherals", "power_budget"), ("غير منفذ بعد",)),
    Laboratory("signal_processing", "signals", "مختبر معالجة الإشارات", "planned",
               ("sampling", "filtering", "fft", "noise_analysis"), ("غير منفذ بعد",)),
    Laboratory("numerical_science", "science", "مختبر الرياضيات والطرق العددية", "planned",
               ("linear_algebra", "optimization", "uncertainty", "sensitivity"), ("غير منفذ بعد",)),
    Laboratory("mechanical_systems", "mechanical", "مختبر الأنظمة الميكانيكية", "planned",
               ("kinematics", "dynamics", "loads", "vibration"), ("غير منفذ بعد",)),
    Laboratory("thermal_fluids", "thermal", "مختبر الحرارة والموائع", "planned",
               ("heat_transfer", "fluid_flow", "thermal_limits"), ("غير منفذ بعد",)),
    Laboratory("materials_structures", "materials", "مختبر المواد والمنشآت", "planned",
               ("stress", "strain", "fatigue", "material_models"), ("غير منفذ بعد",)),
    Laboratory("data_experiments", "data", "مختبر البيانات والتجارب", "planned",
               ("statistics", "reproducibility", "outlier_detection", "confidence_intervals"), ("غير منفذ بعد",)),
    Laboratory("research_validation", "research", "مختبر الفرضيات والمراجع", "planned",
               ("source_tracking", "claim_checking", "evidence_matrix"), ("غير منفذ بعد",)),
)


def list_laboratories(domain=None):
    """Return immutable catalog entries, optionally filtered by domain."""
    if domain is not None and (not isinstance(domain, str) or not domain):
        raise ValueError("domain must be a non-empty string")
    return tuple(lab for lab in _LABS if domain is None or lab.domain == domain)


def select_laboratory(domain, lab_id=None):
    """Resolve only an implemented lab; planned entries are never executable."""
    if not isinstance(domain, str) or not domain:
        raise ValueError("domain must be a non-empty string")
    candidates = [lab for lab in _LABS if lab.domain == domain]
    if lab_id is not None:
        candidates = [lab for lab in candidates if lab.lab_id == lab_id]
    if not candidates:
        raise LookupError("no laboratory is registered for this domain and identifier")
    for lab in candidates:
        if lab.status == "implemented":
            return lab
    raise NotImplementedError("matching laboratory is planned but not implemented")
