"""
Factory Boy factories for test data generation.

Factory Boy is sync by default, but we can use it with async SQLAlchemy
by using the build() strategy and manually saving objects in async context.

Usage with async SQLAlchemy:
    # Option 1: Build + Manual Save
    user = UserFactory.build()
    async with session.begin():
        session.add(user)
    return user

    # Option 2: Async helper (recommended)
    user = await create_user_async(session, username="testuser")
"""

from typing import Any, Optional
import factory
from factory.alchemy import SQLAlchemyModelFactory


class BaseFactory(SQLAlchemyModelFactory):
    """
    Base factory for all SQLAlchemy model factories.

    Note: Factory Boy's SQLAlchemyModelFactory is sync by default.
    For async SQLAlchemy, use the build() strategy and save manually:

        user = UserFactory.build()
        async with session.begin():
            session.add(user)

    Or create an async wrapper helper.
    """

    class Meta:
        sqlalchemy_session = None  # Will be set in tests
        sqlalchemy_session_persistence = "commit"  # Auto-commit on create


# --- Placeholder Factories ---
# These will be expanded as models are implemented.

# Example (uncomment when User model exists):
#
# class UserFactory(BaseFactory):
#     class Meta:
#         model = User
#
#     id = factory.Sequence(lambda n: n + 1)
#     email = factory.Sequence(lambda n: f"user{n}@example.com")
#     username = factory.Sequence(lambda n: f"user{n}")
#     hashed_password = factory.LazyFunction(lambda: "$2b$12$...hashed...")
#     is_active = True
#     created_at = factory.LazyFunction(datetime.utcnow)
#
#     @classmethod
#     def build_user(cls, **kwargs) -> User:
#         """Build user instance without database persistence."""
#         return cls.build(**kwargs)


def async_factory_wrapper(session, factory_class: type, **kwargs) -> Any:
    """
    Helper to use sync factories in async context.

    Usage:
        user = await async_factory_wrapper(session, UserFactory, email="test@test.com")

    Args:
        session: Async SQLAlchemy session
        factory_class: Factory class to use
        **kwargs: Factory field values

    Returns:
        Created model instance
    """
    instance = factory_class.build(**kwargs)
    session.add(instance)
    return instance