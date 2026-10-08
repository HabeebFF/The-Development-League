"""The AI Coach's knowledge base: what staff know about Free Fire, kept apart from match data.

Coaching claims about a team come from match data only; these entries are the general
knowledge (what a Gloo Wall is for, where the Clock Tower is) the coach may add to them.
When an entry and our own match data disagree (a UAV radius, a zone timing), match data wins.
"""

from django.conf import settings
from django.db import models

from common.models import TimeStampedModel


class KnowledgeQuerySet(models.QuerySet):
    def for_coach(self):
        """What the coach may use: entries staff wrote or approved, never drafts."""
        return self.filter(status=KnowledgeEntry.Status.APPROVED).exclude(body="")


class KnowledgeEntry(TimeStampedModel):
    """One piece of general knowledge. Entries researched online arrive as DRAFTs with their
    sources and patch; staff approve, edit or reject them before the coach uses them."""

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    class Origin(models.TextChoices):
        STAFF = "STAFF", "Written by staff"
        RESEARCH = "RESEARCH", "Researched online"

    class Kind(models.TextChoices):
        WEAPON = "WEAPON", "Weapon"
        ATTACHMENT = "ATTACHMENT", "Attachment"
        CHARACTER = "CHARACTER", "Character"
        PET = "PET", "Pet"
        UTILITY = "UTILITY", "Utility"
        MAP = "MAP", "Map, drop spot or route"
        ZONE = "ZONE", "Zone"
        GENERAL = "GENERAL", "General"

    kind = models.CharField(max_length=12, choices=Kind.choices)
    title = models.CharField(max_length=120)
    body = models.TextField(blank=True, help_text="Plain text the coach may quote")
    data = models.JSONField(default=dict, blank=True, help_text="Numbers such as range or duration")
    map = models.ForeignKey(
        "maps.Map", on_delete=models.CASCADE, null=True, blank=True, related_name="knowledge"
    )
    area = models.ForeignKey(
        "maps.MapArea",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="knowledge",
        help_text="The named place this entry is about",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.APPROVED)
    origin = models.CharField(max_length=10, choices=Origin.choices, default=Origin.STAFF)
    sources = models.JSONField(
        default=list, blank=True, help_text="[{title, url, publisher, published, accessed}]"
    )
    patch = models.CharField(
        max_length=20, blank=True, help_text="Game patch it applies to, e.g. OB55"
    )
    conflicts = models.TextField(blank=True, help_text="Where sources (or our data) disagree")
    weak_sources = models.BooleanField(default=False)
    weak_reason = models.CharField(max_length=300, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    objects = KnowledgeQuerySet.as_manager()

    class Meta:
        ordering = ["kind", "map", "title"]
        verbose_name_plural = "knowledge entries"

    def __str__(self) -> str:
        return f"{self.get_kind_display()}: {self.title}"


class WeaponName(TimeStampedModel):
    """The logs give a weapon number per kill; staff name each number once."""

    class WeaponClass(models.TextChoices):
        AR = "AR", "Assault rifle"
        SMG = "SMG", "SMG"
        SHOTGUN = "SHOTGUN", "Shotgun"
        SNIPER = "SNIPER", "Sniper"
        MARKSMAN = "MARKSMAN", "Marksman rifle"
        LMG = "LMG", "LMG"
        PISTOL = "PISTOL", "Pistol"
        MELEE = "MELEE", "Melee"
        THROWABLE = "THROWABLE", "Throwable"
        OTHER = "OTHER", "Other"

    weapon_id = models.IntegerField(unique=True)
    name = models.CharField(max_length=60)
    weapon_class = models.CharField(max_length=10, choices=WeaponClass.choices, blank=True)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["weapon_id"]

    def __str__(self) -> str:
        return f"{self.weapon_id}: {self.name}"


class CoachReport(TimeStampedModel):
    """A team's weekly report: 3 to 5 tasks drawn from its facts, and what changed.

    ``facts`` is the snapshot the tasks cite, so a report keeps its evidence even after
    later matches change the numbers.
    """

    team = models.ForeignKey("league.Team", on_delete=models.CASCADE, related_name="coach_reports")
    week_start = models.DateField(help_text="Monday of the week the report covers")
    matches = models.JSONField(default=list, help_text="[{id, label, map, played_on}] behind it")
    facts = models.JSONField(default=list)
    tasks = models.JSONField(default=list, help_text="[{title, why, facts: [ids], matches}]")
    changes = models.JSONField(default=list, help_text="[{text, better, facts}] vs earlier weeks")
    writer = models.CharField(max_length=40, default="template")
    is_published = models.BooleanField(default=True)
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-week_start", "team__name"]
        unique_together = [("team", "week_start")]

    def __str__(self) -> str:
        return f"{self.team}: week of {self.week_start}"


class CounterPlan(models.Model):
    """How ``team`` can play against ``opponent``, made when first asked for in a week and
    remade when the opponent has played new matches. The plays cite ``facts``."""

    team = models.ForeignKey("league.Team", on_delete=models.CASCADE, related_name="counter_plans")
    opponent = models.ForeignKey("league.Team", on_delete=models.CASCADE, related_name="+")
    week_start = models.DateField()
    matches = models.JSONField(default=list, help_text="The opponent's matches: [{id, label, map}]")
    facts = models.JSONField(default=list)
    plays = models.JSONField(default=list, help_text="[{title, why, facts: [ids], matches}]")
    head_to_head = models.JSONField(default=dict)
    writer = models.CharField(max_length=40, default="template")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-week_start", "opponent__name"]
        unique_together = [("team", "opponent", "week_start")]

    def __str__(self) -> str:
        return f"{self.team} vs {self.opponent}: week of {self.week_start}"


class AiUsage(models.Model):
    """One call to the AI writer: what it cost and how much of its text passed the checks."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    feature = models.CharField(max_length=20, help_text="report or counter")
    provider = models.CharField(max_length=20)
    model = models.CharField(max_length=60)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=10, decimal_places=6, default=0)
    ok = models.BooleanField(default=True)
    error = models.CharField(max_length=300, blank=True)
    items = models.PositiveSmallIntegerField(default=0, help_text="Items asked for")
    kept = models.PositiveSmallIntegerField(default=0, help_text="Items that passed the checks")

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.feature} {self.model}"
