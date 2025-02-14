from django.db import models, transaction
from kabaramadalapeste.conf import settings
from accounts.models import Participant

from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

import random
import logging
import math

from solo.models import SingletonModel
from django.template.defaultfilters import slugify
from enum import Enum
import string
import os

logger = logging.getLogger(__file__)


class Island(models.Model):
    island_id = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=50)
    challenge = models.ForeignKey('Challenge',
                                  on_delete=models.SET_NULL,
                                  blank=True,
                                  null=True)

    peste_guidance = models.TextField(null=True, blank=True)

    class IslandsNotConnected(Exception):
        pass

    def __str__(self):
        return self.name

    @property
    def neighbors(self):
        first_ns = set([way.second_end for way in Way.objects.filter(first_end=self)])
        second_ns = set([way.first_end for way in Way.objects.filter(second_end=self)])
        return first_ns.union(second_ns)

    def is_neighbor_with(self, other_island):
        return (
            Way.objects.filter(first_end=self, second_end=other_island).count() != 0 or
            Way.objects.filter(first_end=other_island, second_end=self).count() != 0
        )


class PesteConfiguration(SingletonModel):
    island_spade_cost = models.IntegerField(default=12000)
    peste_reward = models.IntegerField(default=24000)
    is_peste_available = models.BooleanField(default=False)


class Peste(models.Model):
    island = models.OneToOneField(Island,
                                  on_delete=models.CASCADE)
    is_found = models.BooleanField(default=False)
    found_by = models.ForeignKey('accounts.Participant',
                                 on_delete=models.SET_NULL,
                                 null=True,
                                 blank=True)

    class PesteNotAvailable(Exception):
        pass


class Way(models.Model):
    first_end = models.ForeignKey('Island',
                                  related_name='first_ends',
                                  on_delete=models.CASCADE)
    second_end = models.ForeignKey('Island',
                                   related_name='second_ends',
                                   on_delete=models.CASCADE)

    def __str__(self):
        return 'Way between %s and %s' % (self.first_end, self.second_end)

    class Meta:
        unique_together = (("first_end", "second_end"),)


class Challenge(models.Model):
    challenge_id = models.PositiveIntegerField(unique=True)
    name = models.CharField(max_length=50)
    is_judgeable = models.BooleanField(default=False)

    def __str__(self):
        return '%s | %s' % (self.name, self.challenge_id)

    @property
    def questions(self):
        if self.is_judgeable:
            return self.judgeablequestion
        return self.shortanswerquestion


class ChallengeRewardItem(models.Model):
    reward_type = models.CharField(
        max_length=2,
        choices=settings.GAME_CHALLENGE_REWARD_TYPE_CHOICES,
        default=settings.GAME_SEKKE,
    )
    amount = models.IntegerField(default=0)
    challenge = models.ForeignKey('Challenge',
                                  related_name='rewards',
                                  on_delete=models.SET_NULL,
                                  blank=True,
                                  null=True)

    def __str__(self):
        return '%s %s %s' % (
            self.challenge.name, self.reward_type, self.amount
        )

    class Meta:
        unique_together = (("challenge", "reward_type"),)


class BaseQuestion(models.Model):
    title = models.CharField(max_length=100)
    question = models.FileField(upload_to='soals/')

    challenge = models.ForeignKey('Challenge',
                                  related_name='%(class)s',
                                  on_delete=models.CASCADE)

    class Meta:
        abstract = True

    def __str__(self):
        return '%s for challenge: %s' % (
            self.title, self.challenge.name
        )

    def get_answer_type(self):
        raise NotImplementedError

    def save(self, *args, **kwargs):
        # LONG TODO: fix here so not change every time
        # Call standard save
        super(BaseQuestion, self).save(*args, **kwargs)

        if not settings.TESTING and self.question:
            initial_path = self.question.path

            # New path in the form eg '/images/uploadmodel/1/image.jpg'
            dt = timezone.now()
            r = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            new_n = '-'.join([r, dt.strftime('%H-%M-%S-%f'), os.path.basename(initial_path)])
            new_name = 'soals/' + new_n
            new_path = os.path.join(settings.MEDIA_ROOT, 'soals', new_n)

            # Create dir if necessary and move file
            if not os.path.exists(os.path.dirname(new_path)):
                os.makedirs(os.path.dirname(new_path))

            os.rename(initial_path, new_path)

            # Update the image_file field
            self.question.name = new_name

            # Save changes
            super(BaseQuestion, self).save(*args, **kwargs)


class ShortAnswerQuestion(BaseQuestion):
    INTEGER = 'INT'
    FLOAT = 'FLT'
    STRING = 'STR'
    ANSWER_TYPE_CHOICES = [
        (INTEGER, 'int'),
        (FLOAT, 'float'),
        (STRING, 'string')
    ]
    correct_answer = models.CharField(max_length=100)
    answer_type = models.CharField(
        max_length=3,
        choices=ANSWER_TYPE_CHOICES,
        default=STRING,
    )

    pis_set = GenericRelation(
        'ParticipantIslandStatus',
        related_query_name='short_answer_question',
        content_type_field='question_content_type',
        object_id_field='question_object_id',
    )

    def get_answer_type(self):
        return self.answer_type


class JudgeableQuestion(BaseQuestion):
    upload_required = models.BooleanField(default=True)

    pis_set = GenericRelation(
        'ParticipantIslandStatus',
        related_query_name='judgeable_question',
        content_type_field='question_content_type',
        object_id_field='question_object_id',
    )

    def get_answer_type(self):
        return 'FILE' if self.upload_required else 'NO'


class Treasure(models.Model):
    def __str__(self):
        return 'Treasure %s' % self.id

    def get_keys_persian_string(self):
        n = self.keys.exclude(amount__exact=0).all().count()
        s = ''
        i = 0
        for treasure_key_item in self.keys.exclude(amount__exact=0).all():
            s += '%d عدد %s' % (treasure_key_item.amount, settings.GAME_TRANSLATION_DICT[treasure_key_item.key_type])
            if i < n-2:
                s += '، '
            elif i == n-2:
                s += ' و '
            i += 1
        return s

    def get_rewards_persian_string(self):
        n = self.rewards.exclude(amount__exact=0).all().count()
        s = ''
        i = 0
        for treasure_reward_item in self.rewards.exclude(amount__exact=0).all():
            s += '%d عدد %s' % (treasure_reward_item.amount, settings.GAME_TRANSLATION_DICT[treasure_reward_item.reward_type])
            if i < n-2:
                s += '، '
            elif i == n-2:
                s += ' و '
            i += 1
        return s


class TreasureKeyItem(models.Model):
    key_type = models.CharField(
        max_length=2,
        choices=settings.GAME_TREASURE_KEY_TYPE_CHOICES,
        default=settings.GAME_KEY1,
    )
    amount = models.IntegerField(default=0)
    treasure = models.ForeignKey('Treasure',
                                 related_name='keys',
                                 on_delete=models.CASCADE)


class TreasureRewardItem(models.Model):
    reward_type = models.CharField(
        max_length=3,
        choices=settings.GAME_TREASURE_REWARD_TYPE_CHOICES,
        default=settings.GAME_SEKKE,
    )
    amount = models.IntegerField(default=0)
    treasure = models.ForeignKey('Treasure',
                                 related_name='rewards',
                                 on_delete=models.CASCADE)


class ParticipantPropertyItem(models.Model):
    class PropertyCouldNotBeNegative(Exception):
        pass

    property_type = models.CharField(
        max_length=3,
        choices=settings.GAME_PARTICIPANT_PROPERTY_TYPE_CHOICES,
        default=settings.GAME_SEKKE,
    )
    amount = models.IntegerField(default=0)
    participant = models.ForeignKey(Participant,
                                    related_name='properties',
                                    on_delete=models.CASCADE)

    def __str__(self):
        return '%s of %s for user %s' % (
            self.amount, self.property_type, self.participant.member.email,
        )

    class Meta:
        unique_together = (("participant", "property_type"),)


class ParticipantIslandStatus(models.Model):
    class CantAssignNewQuestion(Exception):
        pass

    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    island = models.ForeignKey(Island, on_delete=models.CASCADE)

    treasure = models.ForeignKey(Treasure, on_delete=models.SET_NULL, null=True)

    is_treasure_visible = models.BooleanField(default=False)

    did_open_treasure = models.BooleanField(default=False)
    treasure_opened_at = models.DateTimeField(null=True)

    currently_in = models.BooleanField(default=False)

    did_reach = models.BooleanField(default=False)
    reached_at = models.DateTimeField(null=True)

    currently_anchored = models.BooleanField(default=False)
    last_anchored_at = models.DateTimeField(null=True)

    did_accept_challenge = models.BooleanField(default=False)
    challenge_accepted_at = models.DateTimeField(null=True)

    did_spade = models.BooleanField(default=False)
    spaded_at = models.DateTimeField(null=True)

    question_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True)
    question_object_id = models.PositiveIntegerField(null=True)
    question = GenericForeignKey('question_content_type', 'question_object_id')

    class Meta:
        unique_together = (("participant", "island"),)
        verbose_name_plural = 'Participant island statuses'

    def assign_question(self, force=False):
        if self.question and not force:
            logger.info('This PIS already has question if you want to forcly change it use force=True')
            return
        all_island_questions = set(self.island.challenge.questions.values_list('id'))
        got_this_challenge_questions = set(ParticipantIslandStatus.objects.filter(
            participant__team=self.participant.team,
            island__challenge=self.island.challenge,
        ).exclude(island=self.island).values_list('question_object_id'))
        valid_question_ids = all_island_questions.difference(got_this_challenge_questions)
        if not valid_question_ids:
            raise ParticipantIslandStatus.CantAssignNewQuestion
        result_question_id = random.choice(list(valid_question_ids))
        self.question = self.island.challenge.questions.get(id=result_question_id[0])
        self.save()

    @property
    def submit(self):
        try:
            if self.question.challenge.is_judgeable:
                return self.judgeablesubmit
            return self.shortanswersubmit
        except (ParticipantIslandStatus.judgeablesubmit.RelatedObjectDoesNotExist,
                ParticipantIslandStatus.shortanswersubmit.RelatedObjectDoesNotExist, AttributeError):
            return None

    def __str__(self):
        return 'ParticipantIslandStatus for %s and %s' % (self.participant, self.island.name)


class BaseSubmit(models.Model):
    class SubmitStatus(models.TextChoices):
        Pending = 'Pending'
        Correct = 'Correct'
        Wrong = 'Wrong'

    pis = models.OneToOneField(ParticipantIslandStatus,
                               related_name='%(class)s',
                               on_delete=models.CASCADE)
    submitted_at = models.DateTimeField(default=timezone.now)
    submit_status = models.CharField(max_length=20, default=SubmitStatus.Pending,
                                     choices=SubmitStatus.choices)
    judged_at = models.DateTimeField(null=True)

    class Meta:
        abstract = True

    def __str__(self):
        return 'Submit from %s for question %s with status %s' % (
            self.pis.participant.member.username, self.pis.question.title, self.submit_status
        )

    def __init__(self, *args, **kwargs):
        super(BaseSubmit, self).__init__(*args, **kwargs)
        self.initial_submit_status = self.submit_status

    def is_bad_change(self, *args, **kwargs):
        if (self.initial_submit_status != BaseSubmit.SubmitStatus.Pending and
                self.initial_submit_status != self.submit_status):
            return True
        return False

    @transaction.atomic
    def give_rewards_to_participant(self):
        for reward in self.pis.question.challenge.rewards.all():
            self.pis.participant.add_property(reward.reward_type, reward.amount)

    def get_rewards_persian(self):
        n = self.pis.question.challenge.rewards.exclude(amount__exact=0).all().count()
        s = ''
        i = 0
        for treasure_reward_item in self.pis.question.challenge.rewards.exclude(amount__exact=0).all():
            s += '%d عدد %s' % (treasure_reward_item.amount, settings.GAME_TRANSLATION_DICT[treasure_reward_item.reward_type])
            if i < n-2:
                s += '، '
            elif i == n-2:
                s += ' و '
            i += 1
        return s


class ShortAnswerSubmit(BaseSubmit):

    submitted_answer = models.CharField(max_length=100)

    def check_answer(self):
        question = self.pis.question
        is_correct = False
        try:
            if question.answer_type == ShortAnswerQuestion.INTEGER:
                is_correct = int(self.submitted_answer) == int(question.correct_answer)
            elif question.answer_type == ShortAnswerQuestion.FLOAT:
                is_correct = math.isclose(float(self.submitted_answer), float(question.correct_answer),
                                          abs_tol=5e-3)
            else:
                is_correct = self.submitted_answer == question.correct_answer
        except ValueError:
            logger.warn('Type mismatch for %s' % self)
        self.submit_status = BaseSubmit.SubmitStatus.Correct if is_correct else BaseSubmit.SubmitStatus.Wrong
        self.judged_at = timezone.now()
        self.save()


class JudgeableSubmit(BaseSubmit):
    submitted_answer = models.FileField(upload_to='answers/', null=True, blank=True)
    judge_note = models.CharField(max_length=200, null=True, blank=True)

    judged_by = models.ForeignKey('accounts.Member',
                                  on_delete=models.SET_NULL,
                                  null=True,
                                  blank=True)

    def save(self, *args, **kwargs):
        # LONG TODO: fix here so not change every time
        # Call standard save
        super(JudgeableSubmit, self).save(*args, **kwargs)

        if not settings.TESTING and self.submitted_answer and len(self.submitted_answer.name) < 40:
            initial_path = self.submitted_answer.path

            # New path in the form eg '/images/uploadmodel/1/image.jpg'
            dt = timezone.now()
            r = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            new_n = '-'.join([r, dt.strftime('%H-%M-%S-%f'), os.path.basename(initial_path)])
            new_name = 'answers/' + new_n
            new_path = os.path.join(settings.MEDIA_ROOT, 'answers', new_n)

            # Create dir if necessary and move file
            if not os.path.exists(os.path.dirname(new_path)):
                os.makedirs(os.path.dirname(new_path))

            os.rename(initial_path, new_path)

            # Update the image_file field
            self.submitted_answer.name = new_name

            # Save changes
            super(JudgeableSubmit, self).save(*args, **kwargs)


class TradeOffer(models.Model):
    creator_participant = models.ForeignKey(Participant, related_name='created_trade_offers', on_delete=models.CASCADE)
    status = models.CharField(
        max_length=2,
        choices=settings.GAME_OFFER_STATUS_CHOICES,
        default=settings.GAME_OFFER_ACTIVE,
    )
    creation_datetime = models.DateTimeField(auto_now_add=True)
    close_datetime = models.DateTimeField(null=True, blank=True)
    accepted_participant = models.ForeignKey(Participant,
                                             related_name='accepted_trade_offers',
                                             on_delete=models.SET_NULL,
                                             null=True,
                                             blank=True)

    def __str__(self):
        return 'creator: %s, status: %s' % (self.creator_participant.member.email, self.status)

    def to_dict(self):
        dic = {
            'pk': self.pk,
            'creator_participant_username': self.creator_participant.team_name,
            'creator_participant_picture_url': self.creator_participant.picture_url
        }
        if self.accepted_participant:
            dic['acceptor_participant_username'] = self.accepted_participant.team_name
            dic['acceptor_participant_picture_url'] = self.accepted_participant.picture_url
        for offer_item in self.suggested_items.all():
            dic['suggested_' + offer_item.property_type] = offer_item.amount
        for offer_item in self.requested_items.all():
            dic['requested_' + offer_item.property_type] = offer_item.amount
        return dic

    def get_requested_items_persian(self):
        n = self.requested_items.exclude(amount__exact=0).all().count()
        s = ''
        i = 0
        for requested_item in self.requested_items.exclude(amount__exact=0).all():
            s += '%d عدد %s' % (requested_item.amount, settings.GAME_TRANSLATION_DICT[requested_item.property_type])
            if i < n-2:
                s += '، '
            elif i == n-2:
                s += ' و '
            i += 1
        return s

    class InvalidOfferSelected(Exception):
        pass


class TradeOfferSuggestedItem(models.Model):
    property_type = models.CharField(
        max_length=3,
        choices=settings.GAME_PARTICIPANT_PROPERTY_TYPE_CHOICES,
        default=settings.GAME_SEKKE,
    )
    amount = models.IntegerField(default=0)
    offer = models.ForeignKey(TradeOffer, related_name='suggested_items', on_delete=models.CASCADE)

    class Meta:
        unique_together = (("offer", "property_type"),)


class TradeOfferRequestedItem(models.Model):
    property_type = models.CharField(
        max_length=3,
        choices=settings.GAME_PARTICIPANT_PROPERTY_TYPE_CHOICES,
        default=settings.GAME_SEKKE,
    )
    amount = models.IntegerField(default=0)
    offer = models.ForeignKey(TradeOffer, related_name='requested_items', on_delete=models.CASCADE)

    class Meta:
        unique_together = (("offer", "property_type"),)


class AbilityUsage(models.Model):
    datetime = models.DateTimeField(auto_now_add=True)
    participant = models.ForeignKey(Participant, related_name='used_abilities', on_delete=models.CASCADE)
    ability_type = models.CharField(
        max_length=3,
        choices=settings.GAME_ABILITY_TYPE_CHOICES,
        default=settings.GAME_VISION,
    )
    is_active = models.BooleanField(default=False)

    class InvalidAbility(Exception):
        pass


class BandargahConfiguration(SingletonModel):
    min_possible_invest = models.IntegerField(default=3000)
    max_possible_invest = models.IntegerField(default=4000)
    profit_coefficient = models.FloatField(default=1.5)
    loss_coefficient = models.FloatField(default=0.5)
    min_interval_investments = models.IntegerField(default=300000)
    max_interval_investments = models.IntegerField(default=1000000)


class BandargahInvestment(models.Model):
    participant = models.ForeignKey(Participant, related_name='investments', on_delete=models.CASCADE)
    amount = models.IntegerField(default=0)
    datetime = models.DateTimeField(auto_now_add=True)
    is_applied = models.BooleanField(default=False)

    class InvalidAmount(Exception):
        pass

    class LocationIsNotBandargah(Exception):
        pass

    class CantInvestTwiceToday(Exception):
        pass


class Bully(models.Model):
    owner = models.ForeignKey(Participant, related_name='bullies', on_delete=models.CASCADE)
    island = models.ForeignKey(Island, related_name='bullies', on_delete=models.CASCADE)
    creation_datetime = models.DateTimeField(auto_now_add=True)
    is_expired = models.BooleanField(default=False)
    expired_datetime = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name_plural = 'Bullies'

    class CantBeOnBandargah(Exception):
        pass


class GameEventLog(models.Model):
    class EventTypes(models.TextChoices):
        Nope = 'Nope'
        SetStart = 'Set start'
        Move = 'Move'
        Anchor = 'Anchor'
        OpenTreasure = 'Open treasure'
        Spade = 'Spade'
        AcceptChallenge = 'Accept challenge'
        CreateOffer = 'Create offer'
        DeleteOffer = 'Delete offer'
        AcceptOffer = 'Accept offer'
        UseAbility = 'Use ability'
        Invest = 'Invest'
        Submit = 'Submit'
        BullyTarget = 'Bully target'

    who = models.ForeignKey(Participant, related_name='logs', on_delete=models.DO_NOTHING)
    when = models.DateTimeField()
    where = models.ForeignKey(Island, related_name='logs', on_delete=models.DO_NOTHING, null=True)
    event_type = models.CharField(max_length=20, default=EventTypes.Nope,
                                  choices=EventTypes.choices)

    related_content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True)
    related_object_id = models.PositiveIntegerField(null=True)
    related = GenericForeignKey('related_content_type', 'related_object_id')
