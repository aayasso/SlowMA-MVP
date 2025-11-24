"""
Authentication Manager
Handles user authentication with Supabase
"""

import os
from supabase import create_client, Client
from dotenv import load_dotenv
from typing import Optional, Dict, Any
import json

load_dotenv()


class AuthManager:
    """Manages user authentication and session"""
    
    def __init__(self):
        """Initialize Supabase client"""
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_ANON_KEY')
        
        if not supabase_url or not supabase_key:
            raise ValueError("Supabase credentials not found in environment variables")
        
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.current_user = None
    
    # ==================== SIGN UP ====================
    
    def sign_up_email(self, email: str, password: str, username: Optional[str] = None) -> Dict[str, Any]:
        """
        Sign up new user with email and password
        
        Args:
            email: User's email
            password: User's password (min 6 characters)
            username: Optional username
            
        Returns:
            Dict with success status and user data or error message
        """
        try:
            # Create auth user using correct syntax
            response = self.supabase.auth.sign_up(
                credentials={
                    "email": email,
                    "password": password
                }
            )
            
            if response.user:
                # Create user profile
                profile_data = {
                    "id": response.user.id,
                    "email": email,
                    "username": username,
                    "housen_stage": 1,
                    "housen_substage": 1,
                    "journeys_completed": 0,
                    "total_time_seconds": 0,
                    "museum_visits": 0,
                    "notifications_enabled": True,
                    "location_permission": False
                }
                
                self.supabase.table('user_profiles').insert(profile_data).execute()
                
                return {
                    "success": True,
                    "user": response.user,
                    "session": response.session,
                    "message": "Account created successfully!"
                }
            else:
                return {
                    "success": False,
                    "error": "Failed to create account"
                }
                
        except Exception as e:
            error_msg = str(e)
            # Make error messages more user-friendly
            if "already registered" in error_msg.lower():
                error_msg = "This email is already registered. Try signing in instead."
            elif "invalid email" in error_msg.lower():
                error_msg = "Please enter a valid email address."
            elif "password" in error_msg.lower():
                error_msg = "Password must be at least 6 characters."
                
            return {
                "success": False,
                "error": error_msg
            }
    
    # ==================== SIGN IN ====================
    
    def sign_in_email(self, email: str, password: str) -> Dict[str, Any]:
        """
        Sign in with email and password
        
        Args:
            email: User's email
            password: User's password
            
        Returns:
            Dict with success status and user data or error message
        """
        try:
            response = self.supabase.auth.sign_in_with_password(
                credentials={
                    "email": email,
                    "password": password
                }
            )
            
            if response.user:
                self.current_user = response.user
                
                return {
                    "success": True,
                    "user": response.user,
                    "session": response.session
                }
            else:
                return {
                    "success": False,
                    "error": "Invalid email or password"
                }
                
        except Exception as e:
            error_msg = str(e)
            if "invalid" in error_msg.lower() or "credentials" in error_msg.lower():
                error_msg = "Invalid email or password"
                
            return {
                "success": False,
                "error": error_msg
            }
    
    def sign_in_magic_link(self, email: str) -> Dict[str, Any]:
        """
        Send magic link to email for passwordless sign in
        
        Args:
            email: User's email
            
        Returns:
            Dict with success status
        """
        try:
            response = self.supabase.auth.sign_in_with_otp(
                credentials={
                    "email": email
                }
            )
            
            return {
                "success": True,
                "message": "Magic link sent! Check your email."
            }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def sign_in_google(self) -> Dict[str, Any]:
        """
        Initiate Google OAuth sign in
        
        Returns:
            Dict with auth URL for redirect
        """
        try:
            response = self.supabase.auth.sign_in_with_oauth(
                provider="google"
            )
            
            return {
                "success": True,
                "url": response.url
            }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== SIGN OUT ====================
    
    def sign_out(self) -> Dict[str, Any]:
        """Sign out current user"""
        try:
            self.supabase.auth.sign_out()
            self.current_user = None
            
            return {
                "success": True,
                "message": "Signed out successfully"
            }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== SESSION MANAGEMENT ====================
    
    def get_session(self) -> Optional[Dict[str, Any]]:
        """Get current session"""
        try:
            session = self.supabase.auth.get_session()
            return session
        except:
            return None
    
    def get_user(self) -> Optional[Dict[str, Any]]:
        """Get current authenticated user"""
        try:
            user = self.supabase.auth.get_user()
            return user.user if user else None
        except:
            return None
    
    def refresh_session(self) -> Dict[str, Any]:
        """Refresh authentication session"""
        try:
            response = self.supabase.auth.refresh_session()
            
            return {
                "success": True,
                "session": response.session
            }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    # ==================== USER PROFILE ====================
    
    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user profile from database
        
        Args:
            user_id: User's UUID
            
        Returns:
            User profile data or None
        """
        try:
            response = self.supabase.table('user_profiles').select('*').eq('id', user_id).execute()
            
            if response.data and len(response.data) > 0:
                return response.data[0]
            return None
                
        except Exception as e:
            print(f"Error getting user profile: {e}")
            return None
    
    def update_user_profile(self, user_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update user profile
        
        Args:
            user_id: User's UUID
            updates: Dict of fields to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.supabase.table('user_profiles').update(updates).eq('id', user_id).execute()
            return True
                
        except Exception as e:
            print(f"Error updating user profile: {e}")
            return False
    
    # ==================== PASSWORD MANAGEMENT ====================
    
    def reset_password_email(self, email: str) -> Dict[str, Any]:
        """
        Send password reset email
        
        Args:
            email: User's email
            
        Returns:
            Dict with success status
        """
        try:
            self.supabase.auth.reset_password_email(email)
            
            return {
                "success": True,
                "message": "Password reset email sent"
            }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def update_password(self, new_password: str) -> Dict[str, Any]:
        """
        Update password for current user
        
        Args:
            new_password: New password
            
        Returns:
            Dict with success status
        """
        try:
            self.supabase.auth.update_user(
                attributes={
                    "password": new_password
                }
            )
            
            return {
                "success": True,
                "message": "Password updated successfully"
            }
                
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }