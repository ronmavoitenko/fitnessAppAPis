from datetime import timedelta
from django.shortcuts import get_object_or_404

from django.utils import timezone
from drf_yasg.utils import swagger_auto_schema, no_body
from rest_framework import filters
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.tasks.models import Task
from apps.tasks.serializers import GetTaskSerializer
from apps.activity.models import Plan, ActivitySleep, ActivityWater, ActivityFood, ActivityStep
from apps.activity.serializers import PlanSerializer, SleepSerializer, WaterSerializer, CreateFoodSerializer,\
    CreateStepsSerializer, GetAllStepsSerializer, GetAllCaloriesSerializer


class PlanViewSet(viewsets.ModelViewSet):
    queryset = Plan.objects.all()
    filter_backends = [filters.OrderingFilter]
    ordering = ['id']
    serializer_class = PlanSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, "swagger_fake_view", False):
            return Plan.objects.none()
        if self.action == "my_tasks":
            return self.request.user.plan.tasks.all().order_by("id")

        return queryset

    def perform_create(self, serializer):
        plan = serializer.save()
        self.request.user.plan = plan
        self.request.user.save()

    @action(methods=['patch'], detail=False, serializer_class=PlanSerializer, url_path="change")
    def change_plan(self, request, *args, **kwargs):
        plan = Plan.objects.get(id=request.user.plan.id)
        plan.steps = request.data["steps"]
        plan.calories = request.data["calories"]
        plan.sleep = request.data["sleep"]
        plan.water = request.data["water"]
        plan.save()
        return Response({"success": True}, status.HTTP_200_OK)

    @action(methods=['post'], detail=False, serializer_class=SleepSerializer, url_path="sleep")
    def create_sleep(self, request, *args, **kwargs):
        sleep = request.data["sleep"]
        plan = self.request.user.plan
        ActivitySleep.objects.create(sleep=sleep, plan=plan)
        return Response({"success": True}, status.HTTP_201_CREATED)

    @action(methods=['post'], detail=False, serializer_class=WaterSerializer, url_path="water")
    def create_water(self, request, *args, **kwargs):
        sleep = request.data["water"]
        plan = self.request.user.plan
        ActivityWater.objects.create(water=sleep, plan=plan)
        return Response({"success": True}, status.HTTP_201_CREATED)

    @action(methods=['post'], detail=False, serializer_class=CreateFoodSerializer, url_path="food")
    def create_food(self, request, *args, **kwargs):
        plan = self.request.user.plan
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(plan=plan)
        return Response({"success": True}, status.HTTP_201_CREATED)

    @action(methods=['delete'], detail=True, serializer_class=None, url_path="delete-food")
    def delete_food(self, *args, **kwargs):
        food_id = kwargs.get("pk")
        food = ActivityFood.objects.get(id=food_id)
        food.delete()
        return Response({"success": True}, status.HTTP_200_OK)

    @action(methods=['get'], detail=False, serializer_class=GetAllCaloriesSerializer, url_path="calories")
    def foods(self, request, *args, **kwargs):
        foods = ActivityFood.objects.filter(plan=self.request.user.plan, created_at__date=timezone.now()).order_by("-id")
        foods_serializer = CreateFoodSerializer(foods, many=True)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        total_calories = serializer.data['all_calories']
        response_data = {
            'all_calories': total_calories,
            'foods': foods_serializer.data
        }
        return Response(response_data, status=status.HTTP_200_OK)

    @action(methods=['post'], detail=False, serializer_class=CreateStepsSerializer, url_path="step")
    def create_step(self, request, *args, **kwargs):
        plan = self.request.user.plan
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(plan=plan)
        return Response({"success": True}, status.HTTP_201_CREATED)

    @action(methods=['get'], detail=False, serializer_class=GetAllStepsSerializer, url_path="steps")
    def steps(self, request, *args, **kwargs):
        steps = ActivityStep.objects.filter(plan=self.request.user.plan, created_at__date=timezone.now()).order_by("-id")
        steps_serializer = CreateStepsSerializer(steps, many=True)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        total_steps = serializer.data['all_steps']
        response_data = {
            'all_steps': total_steps,
            'steps': steps_serializer.data
        }
        return Response(response_data, status=status.HTTP_200_OK)

    @action(methods=['get'], detail=False, serializer_class=GetTaskSerializer, url_path="tasks")
    def my_tasks(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @action(methods=['post'], detail=True, serializer_class=None, url_path="add-to-tasks")
    def add_to_my_tasks(self, *args, **kwargs):
        task = get_object_or_404(Task, pk=kwargs.get("pk"))
        plan = self.request.user.plan
        plan.tasks.add(task)
        plan.save()
        return Response({"success": True}, status.HTTP_200_OK)

    @action(methods=['delete'], detail=True, serializer_class=None, url_path="delete-from-tasks")
    def delete_from_my_tasks(self, *args, **kwargs):
        task = get_object_or_404(Task, pk=kwargs.get("pk"))
        plan = self.request.user.plan
        plan.tasks.remove(task)
        plan.save()
        return Response({"success": True}, status.HTTP_200_OK)

    @swagger_auto_schema(request_body=no_body)
    @action(methods=['put'], detail=True, serializer_class=None, url_path="start-task")
    def start_task(self, *args, **kwargs):
        task = Task.objects.get(id=kwargs.get("pk"))
        plan = self.request.user.plan
        task_exists = plan.tasks.filter(id=task.id).exists()
        if task_exists:
            plan.started_task = task
            plan.start_task = timezone.now()
            plan.save()
            return Response({"success": True}, status.HTTP_200_OK)
        return Response({"success": False}, status.HTTP_200_OK)

    @swagger_auto_schema(request_body=no_body)
    @action(methods=['put'], detail=False, serializer_class=None, url_path="continue-task")
    def continue_task(self, *args, **kwargs):
        plan = self.request.user.plan
        task = plan.started_task
        task_duration = timedelta(hours=task.duration.hour, minutes=task.duration.minute)
        time_elapsed = plan.end_task - plan.start_task
        if time_elapsed < task_duration:
            plan.end_task = None
            plan.save()
        return Response({"success": True}, status.HTTP_200_OK)

    @swagger_auto_schema(request_body=no_body)
    @action(methods=['put'], detail=False, serializer_class=None, url_path="cancel-task")
    def cancel_task(self, *args, **kwargs):
        plan = self.request.user.plan
        plan.start_task = None
        plan.end_task = None
        plan.started_task = None
        plan.save()
        return Response({"success": True}, status.HTTP_200_OK)

    @swagger_auto_schema(request_body=no_body)
    @action(methods=['put'], detail=False, serializer_class=None, url_path="stop-task")
    def stop_task(self, *args, **kwargs):
        plan = self.request.user.plan
        task = plan.started_task
        if task:
            plan.end_task = timezone.now()
            plan.save()
            time_elapsed = plan.end_task - plan.start_task
            task_duration = timedelta(hours=task.duration.hour, minutes=task.duration.minute)
            if time_elapsed > task_duration:
                plan.start_task = None
                plan.started_task = None
                plan.end_task = None
                plan.tasks.remove(task)
                plan.save()
                return Response("You finished your task", status.HTTP_200_OK)
            return Response("Task was stopped", status.HTTP_200_OK)
        return Response("No one task is started", status.HTTP_200_OK)
