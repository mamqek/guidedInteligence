# Abstract class responsibilities

When tracing abstract classes, it helps to think of two responsibilities rather than one feature-sized operation. The front end recognizes the abstract modifier while reading class and member declarations and records that information on the compiler's internal declaration. Later semantic analysis decides whether a use is legal, such as trying to create an abstract class or leaving required members unresolved in a concrete subclass. Keeping those concerns separate lets syntax reading remain structural while the later phase reasons about types and inheritance.
