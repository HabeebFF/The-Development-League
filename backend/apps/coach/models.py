"""The AI Coach's knowledge base: what staff know about Free Fire, kept apart from match data.

Coaching claims about a team come from match data only; these entries are the general
knowledge (what a Gloo Wall is for, where the Clock Tower is) the coach may add to them.
"""

from django.conf import settings
from django.db import models

from common.models import TimeStampedModel


class KnowledgeEntry(TimeStampedModel):
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
